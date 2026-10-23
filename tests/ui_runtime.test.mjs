// 执行实际app.js，使用轻量DOM与可控网络检查乱序、重连和只读回放。
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import { test } from "node:test";
import assert from "node:assert/strict";

const source = await readFile(new URL("../chessarena/web/ui/app.js", import.meta.url), "utf8");
const replaySource = await readFile(new URL("../chessarena/web/ui/replay.js", import.meta.url), "utf8");
const replayModule = await import("data:text/javascript;base64," + Buffer.from(replaySource).toString("base64"));
const FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const state = (game_id, revision) => ({ game_id, revision, fen: FEN, turn: "w", ply: 0, over: false,
  human: { w: true, b: true }, white: "A", black: "B", start_fen: FEN, history_san: [] });
const game = name => ({ headers: { White: name, Black: "B", Event: "Test" }, result: "*", pgn: "*",
  moves: [{ uci: "e2e4", san: "e4", side: "w", fullmove_number: 1 }],
  frames: [{ fen: FEN, turn: "w" }, { fen: FEN, turn: "b" }] });
const response = data => ({ ok: true, json: async () => data });
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; };

class Element {
  constructor() {
    this.children = []; this.value = ""; this.textContent = ""; this.scrollTop = 0;
    this.listeners = new Map(); this.attributes = new Map(); this.nested = new Map(); this.dataset = {};
    this.classList = { add() {}, remove() {}, toggle() {} };
  }
  get options() { return this.children; }
  add(option) { this.children.push(option); }
  addEventListener(name, callback) { this.listeners.set(name, callback); }
  appendChild(element) { this.children.push(element); }
  replaceChildren(...children) { this.children = children; this.value = children[0]?.value || ""; }
  setAttribute(name, value) { this.attributes.set(name, value); }
  querySelector(selector) {
    if (selector === ".last") return null;
    if (!this.nested.has(selector)) this.nested.set(selector, new Element());
    return this.nested.get(selector);
  }
}

async function setup() {
  const elements = new Map(), sockets = [], timers = new Map(), intervals = [];
  let timerId = 0;
  const element = selector => {
    if (!elements.has(selector)) elements.set(selector, new Element());
    return elements.get(selector);
  };
  const clock = { setTimeout: callback => { timers.set(++timerId, callback); return timerId; }, clearTimeout: id => timers.delete(id) };
  const ground = { current: {}, set(config) { this.current = config; }, redrawAll() {} };
  class Socket {
    static OPEN = 1; static CONNECTING = 0;
    constructor() { this.readyState = 0; sockets.push(this); }
    send() {}
  }
  const sandbox = {
    console, Date, Map, Set, Number, String, Boolean, JSON,
    location: { protocol: "http:", host: "localhost" },
    document: { querySelector: element, querySelectorAll: () => [], createElement: () => new Element() },
    Option: class { constructor(text, value) { this.textContent = text; this.value = String(value); } },
    Chessground: () => ground, WebSocket: Socket,
    ReplayPlayer: class extends replayModule.ReplayPlayer { constructor(onChange) { super(onChange, clock); } },
    replayState: replayModule.replayState, moveRows: replayModule.moveRows,
    fetch: async url => response(url === "/players" ? {} : { records: [] }),
    ...clock, setInterval(callback, ms) { intervals.push({ callback, ms }); },
  };
  vm.createContext(sandbox);
  vm.runInContext(source.replace(/^import .+;\r?$/gm, "") +
    "\nglobalThis.app = {ui, replay, applyState, setMode, control, sendMove, onUserMove, connect, importReplay, refreshRecords};", sandbox);
  await Promise.resolve(); await Promise.resolve();
  const hello = snapshot => sockets.at(-1).onmessage({ data: JSON.stringify({ type: "hello", state: snapshot }) });
  return { app: sandbox.app, sandbox, element, sockets, hello, ground, intervals };
}

test("new server hello accepts a lower revision after restart", async () => {
  const { app, hello } = await setup();
  hello(state("old-server", 100));
  hello(state("new-server", 0));
  assert.equal(app.ui.state.game_id, "new-server");
  assert.equal(app.ui.state.revision, 0);
});

test("HTTP responses from before reconnect cannot overwrite the new session", async () => {
  const { app, sandbox, hello } = await setup();
  hello(state("old-server", 100));
  const pending = deferred();
  sandbox.fetch = () => pending.promise;
  const control = app.control({ action: "pause" });
  hello(state("new-server", 0));
  pending.resolve(response({ state: state("old-server", 101) }));
  await control;
  assert.equal(app.ui.state.game_id, "new-server");
});

test("move responses from before reconnect are ignored", async () => {
  const { app, sandbox, hello } = await setup();
  hello(state("old-server", 100));
  const pending = deferred();
  sandbox.fetch = () => pending.promise;
  const move = app.sendMove("e2e4");
  hello(state("new-server", 0));
  pending.resolve(response({ result: { ok: true }, state: state("old-server", 101) }));
  await move;
  assert.equal(app.ui.state.game_id, "new-server");
});

test("a watchdog response from before reconnect cannot restore the old game", async () => {
  const { app, sandbox, sockets, hello, intervals } = await setup();
  hello(state("old-server", 100));
  sockets[0].readyState = 1;
  app.ui.lastMsgAt = 0;
  const pending = deferred();
  sandbox.fetch = () => pending.promise;
  intervals.find(interval => interval.ms === 3000).callback();
  hello(state("new-server", 0));
  pending.resolve(response(state("old-server", 101)));
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(app.ui.state.game_id, "new-server");
});

test("within one connection stale snapshots are dropped and newer undo snapshots apply", async () => {
  const { app, hello } = await setup();
  hello({ ...state("live", 100), ply: 8 });
  app.applyState({ ...state("live", 99), ply: 7 });
  assert.equal(app.ui.state.ply, 8);
  app.applyState({ ...state("live", 101), ply: 6 });
  assert.equal(app.ui.state.ply, 6);
});

test("an old socket cannot disconnect or update its replacement", async () => {
  const { app, sockets } = await setup();
  const old = sockets[0];
  old.readyState = 2;
  app.connect();
  const current = sockets[1];
  old.onclose();
  assert.equal(app.ui.ws, current);
  old.onmessage({ data: JSON.stringify({ type: "hello", state: state("stale", 999) }) });
  assert.equal(app.ui.state, null);
});

test("only the latest import is applied and a failed import preserves the game", async () => {
  const { app, element } = await setup();
  app.setMode("replay");
  const old = deferred();
  const first = app.importReplay("old", () => old.promise);
  await app.importReplay("new", async () => response({ games: [game("New")] }));
  old.resolve(response({ games: [game("Old")] }));
  await first;
  assert.equal(app.replay.game.headers.White, "New");
  app.replay.seek(1);
  await app.importReplay("broken", async () => ({ ok: false, json: async () => ({ error: "Invalid PGN" }) }));
  assert.equal(app.replay.game.headers.White, "New");
  assert.equal(app.replay.ply, 1);
  assert.equal(element("#replay-error").textContent, "Invalid PGN");
});

test("a stale failed refresh does not report an error after a newer success", async () => {
  const { app, sandbox, element } = await setup();
  const pending = deferred();
  sandbox.fetch = () => pending.promise;
  const first = app.refreshRecords();
  sandbox.fetch = async () => response({ records: [{ id: "runs/new.pgn" }] });
  await app.refreshRecords();
  pending.reject(new Error("outdated request"));
  await first;
  assert.equal(element("#toast").textContent, "");
  assert.equal(element("#replay-record").options[1].value, "runs/new.pgn");
});

test("refresh preserves the record chosen while the request was in flight", async () => {
  const { app, sandbox, element } = await setup();
  const pending = deferred();
  sandbox.fetch = () => pending.promise;
  const refresh = app.refreshRecords();
  element("#replay-record").value = "runs/chosen.pgn";
  pending.resolve(response({ records: [{ id: "runs/chosen.pgn" }] }));
  await refresh;
  assert.equal(element("#replay-record").value, "runs/chosen.pgn");
});

test("replay rejects live commands and new live snapshots only update the cache", async () => {
  const { app, sandbox, ground } = await setup();
  const requests = [];
  sandbox.fetch = async (url, options) => { requests.push({ url, options }); return response({ records: [] }); };
  app.applyState(state("live", 1));
  app.setMode("replay");
  app.replay.load([game("Recorded")]);
  const before = ground.current;
  await app.control({ action: "new" }); await app.sendMove("e2e4");
  app.applyState(state("live", 2));
  assert.equal(requests.some(request => request.options?.method === "POST"), false);
  assert.equal(ground.current, before);
  assert.equal(app.ui.state.revision, 2);
  app.setMode("live");
  assert.equal(ground.current.viewOnly, false);
});

test("a pending promotion is canceled when the referee resets the position", async () => {
  const { app } = await setup();
  const snapshot = { ...state("live", 1), fen: "7k/P7/8/8/8/8/8/7K w - - 0 1",
    board: Array.from({ length: 8 }, () => Array(8).fill(".")) };
  snapshot.board[1][0] = "P";
  app.applyState(snapshot);
  app.onUserMove("a7", "a8");
  assert.equal(app.ui.pendingPromo.base, "a7a8");
  app.applyState({ ...snapshot, revision: 2 });
  assert.equal(app.ui.pendingPromo, null);
});
