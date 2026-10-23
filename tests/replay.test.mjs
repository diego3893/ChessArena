// 无需npm安装；运行：node --test tests/replay.test.mjs
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import assert from "node:assert/strict";
const code = await readFile(new URL("../chessarena/web/ui/replay.js", import.meta.url), "utf8");
const { ReplayPlayer, replayState, moveRows } = await import("data:text/javascript;base64," + Buffer.from(code).toString("base64"));

const game = (length = 3) => ({ headers: { White: "A", Black: "B" }, result: "*",
  moves: Array.from({ length }, (_, i) => ({ san: `move${i}`, side: i % 2 ? "b" : "w", fullmove_number: Math.floor(i / 2) + 1 })),
  frames: Array.from({ length: length + 1 }, (_, i) => ({ fen: `fen${i}`, turn: i % 2 ? "b" : "w" })) });
function setup() {
  const pending = new Map();
  let id = 0, changes = 0;
  const player = new ReplayPlayer(() => changes++, {
    setTimeout: (callback, delay) => { pending.set(++id, { callback, delay }); return id; },
    clearTimeout: id => pending.delete(id),
  });
  const tick = () => { const [id, timer] = pending.entries().next().value; pending.delete(id); timer.callback(); };
  return { player, pending, tick, changes: () => changes };
}
test("empty player and zero-move records never start a timer", () => {
  const { player, pending } = setup();
  assert.equal(player.frame, null);
  player.play();
  player.load([game(0)]);
  player.play();
  assert.equal(pending.size, 0);
  assert.equal(player.playing, false);
  assert.equal(replayState(player).over, true);
});
test("play advances one ply, stops at end and can restart", () => {
  const { player, pending, tick } = setup();
  player.load([game()]);
  player.play(); player.play();
  assert.equal(pending.size, 1);
  tick(); assert.equal(player.ply, 1);
  tick(); tick();
  assert.equal(player.ply, 3);
  assert.equal(player.playing, false);
  assert.equal(pending.size, 0);
  player.play();
  assert.equal(player.ply, 0);
  assert.equal(player.playing, true);
});
test("pause and manual seek cancel pending playback", () => {
  const { player, pending } = setup();
  player.load([game()]); player.play(); player.pause();
  assert.equal(pending.size, 0);
  player.play(); player.seek(2);
  assert.equal(player.ply, 2);
  assert.equal(player.playing, false);
  assert.equal(pending.size, 0);
  player.seek(999); assert.equal(player.ply, 3);
  player.seek(-1); assert.equal(player.ply, 0);
  player.seek(NaN); assert.equal(player.ply, 0);
});
test("game switch and import reset cursor and timer", () => {
  const { player, pending } = setup();
  player.load([game(), game(2)]); player.play(); player.selectGame(1);
  assert.equal(player.gameIndex, 1);
  assert.equal(player.ply, 0);
  assert.equal(pending.size, 0);
  player.selectGame(200); assert.equal(player.gameIndex, 1);
  player.play(); player.load([game(1)]);
  assert.equal(player.gameIndex, 0);
  assert.equal(pending.size, 0);
});
test("speed updates active timer without duplicate ticks", () => {
  const { player, pending, tick } = setup();
  player.load([game()]); player.play(); player.setSpeed(4);
  assert.equal(pending.size, 1);
  assert.equal([...pending.values()][0].delay, 200);
  tick(); assert.equal(player.ply, 1);
  player.setSpeed(0); assert.equal(player.speed, 4);
});
test("view state never writes frames, headers or the recorded result", () => {
  const { player } = setup();
  const original = game(); const before = JSON.stringify(original);
  player.load([original]); player.seek(3);
  const state = replayState(player);
  assert.equal(state.fen, "fen3"); assert.equal(state.over, true);
  assert.equal(state.result, "*"); assert.equal(state.white, "A");
  assert.equal(JSON.stringify(original), before);
});
test("move rows preserve black-first FEN numbering", () => {
  assert.deepEqual(moveRows([{ san: "Kg7", side: "b", fullmove_number: 17 }, { san: "Rh7+", side: "w", fullmove_number: 18 }]), [
    { number: 17, w: null, b: { san: "Kg7", ply: 1 } },
    { number: 18, w: { san: "Rh7+", ply: 2 }, b: null },
  ]);
});
