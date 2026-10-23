// ChessArena 前端：chessground 只负责画，规则与真相全在 Python 那侧。
// 协议见 docs/chessarena-API总表.md §16。
import { Chessground } from "/vendor/chessground/dist/chessground.min.js";

const $ = (sel) => document.querySelector(sel);
const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const PIECE_GLYPH = { p: "♟", n: "♞", b: "♝", r: "♜", q: "♛", k: "♚" };
const REASON_TEXT = {
  checkmate: "将杀", stalemate: "逼和", threefold: "三次重复", fifty: "50 步规则",
  insufficient: "子力不足", resign: "认输", timeout: "超时",
  retry_exhausted: "重试次数用尽", forfeit: "弃权", error: "程序异常",
};

const ui = {
  state: null,
  ground: null,
  orientation: "white",
  pendingPromo: null,
  ws: null,
  toastTimer: null,
};

// ---------------------------------------------------------------- 工具
const colorOf = (st) => (st.turn === "w" ? "white" : "black");
const humanOf = (st, side) => Boolean(st.human && st.human[side]);
const canMove = (st) => !st.over && !st.paused && humanOf(st, st.turn);

function destMap(st) {
  const map = new Map();
  for (const mv of st.legal_moves) {
    const from = mv.slice(0, 2);
    const to = mv.slice(2, 4);
    if (!map.has(from)) map.set(from, []);
    const arr = map.get(from);
    if (!arr.includes(to)) arr.push(to);
  }
  return map;
}

function toast(text, kind = "") {
  const el = $("#toast");
  el.textContent = text;
  el.className = "toast " + kind;
  clearTimeout(ui.toastTimer);
  ui.toastTimer = setTimeout(() => el.classList.add("hidden"), 2600);
}

function setConn(ok) {
  const el = $("#conn");
  el.textContent = ok ? "已连接" : "断开 · 重连中";
  el.className = "conn " + (ok ? "ok" : "bad");
}

// ---------------------------------------------------------------- 渲染
function render(st) {
  ui.state = st;
  const turn = colorOf(st);

  ui.ground.set({
    fen: st.fen,
    orientation: ui.orientation,
    turnColor: turn,
    check: st.is_check ? turn : false,
    lastMove: st.last_move ? [st.last_move.slice(0, 2), st.last_move.slice(2, 4)] : [],
    movable: {
      free: false,
      color: canMove(st) ? turn : undefined,
      dests: canMove(st) ? destMap(st) : new Map(),
      showDests: true,
    },
  });

  renderPlayers(st);
  renderMoves(st);
  renderCaptures(st);
  renderStatus(st);
  syncMode(st);
  syncSpeed(st);
  if (st.over) showOver(st);
  else hideOver();
}

function renderPlayers(st) {
  for (const side of ["white", "black"]) {
    const el = $(`#player-${side}`);
    const key = side === "white" ? "w" : "b";
    const name = (side === "white" ? st.white : st.black) || "—";
    el.querySelector(".pname").textContent = name;
    const badge = humanOf(st, key) ? "人" : "AI";
    el.querySelector(".badge").textContent = badge;
    el.classList.toggle("active", !st.over && st.turn === key);
  }
}

function renderMoves(st) {
  const list = $("#moves");
  const sans = st.history_san || [];
  const rows = [];
  for (let i = 0; i < sans.length; i += 2) {
    rows.push([i / 2 + 1, sans[i] || "", sans[i + 1] || ""]);
  }
  list.innerHTML = rows
    .map(([no, w, b], idx) => {
      const lastWhite = idx === rows.length - 1 && sans.length % 2 === 1;
      const lastBlack = idx === rows.length - 1 && sans.length % 2 === 0;
      return `<li><span class="no">${no}.</span>
        <span class="san ${lastWhite ? "last" : ""}">${w}</span>
        <span class="san ${lastBlack ? "last" : ""}">${b}</span></li>`;
    })
    .join("");
  if (list.scrollHeight) list.scrollTop = list.scrollHeight;
}

function renderCaptures(st) {
  const cap = st.captured || { w: [], b: [] };
  const glyph = (sym) => PIECE_GLYPH[String(sym).toLowerCase()] || "";
  const byWhite = (cap.w || []).map(glyph).join(""); // 白方吃掉的黑子
  const byBlack = (cap.b || []).map(glyph).join(""); // 黑方吃掉的白子
  $("#captures").innerHTML =
    `<span class="white-cap">白吃 ${byWhite || "—"}</span> ` +
    `<span class="black-cap">黑吃 ${byBlack || "—"}</span>`;
}

function renderStatus(st) {
  $("#turn-dot").className = "dot " + colorOf(st);
  const name = colorOf(st) === "white" ? "白方" : "黑方";
  if (st.over) {
    const result = st.result || "*";
    const text = result === "1/2-1/2" ? "和棋" : result === "1-0" ? "白方胜" : "黑方胜";
    $("#turn-text").textContent = `${text} · ${REASON_TEXT[st.over_reason] || st.over_reason || ""}`;
  } else if (st.paused) {
    $("#turn-text").textContent = "已暂停";
  } else if (st.is_check) {
    $("#turn-text").textContent = `${name}走棋 · 将军！`;
  } else {
    $("#turn-text").textContent = `${name}走棋`;
  }
  $("#ply-text").textContent = `第 ${st.ply} 步`;
  $("#limit-text").textContent = st.timeout ? `每步限时 ${st.timeout.toFixed(1)}s` : "";
}

function syncMode(st) {
  const oneHuman = humanOf(st, "w") !== humanOf(st, "b");
  for (const btn of document.querySelectorAll("#modes button")) {
    const want = btn.dataset.mode === "hva" ? oneHuman : !oneHuman;
    btn.classList.toggle("active", want);
  }
  $("#speed-group").hidden = oneHuman;
}

function syncSpeed(st) {
  const shown = Number(st.speed || 1);
  for (const btn of document.querySelectorAll("#speed-group button[data-speed]")) {
    btn.classList.toggle("active", Math.abs(Number(btn.dataset.speed) - shown) < 0.001);
  }
  const pause = $("#btn-pause");
  pause.textContent = st.paused ? "继续" : "暂停";
}

// ---------------------------------------------------------------- 落子
async function sendMove(move) {
  try {
    const res = await fetch("/move", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ move }),
    });
    const body = await res.json();
    if (body.result && !body.result.ok) toast(body.result.reason, "bad");
    if (body.state) render(body.state);
  } catch (err) {
    toast("网络错误：" + err.message, "bad");
    if (ui.state) render(ui.state);
  }
}

function onUserMove(orig, dest) {
  const st = ui.state;
  if (!st || !canMove(st)) {
    setTimeout(() => ui.state && render(ui.state), 0); // 弹回
    return;
  }
  const base = orig + dest;
  const promos = st.legal_moves.filter((m) => m.startsWith(base) && m.length === 5);
  if (promos.length) {
    ui.pendingPromo = { base };
    $("#promo").classList.remove("hidden");
    setTimeout(() => ui.state && render(ui.state), 0); // 先退回原位，等选择
    return;
  }
  sendMove(base);
}

function bindPromo() {
  for (const btn of document.querySelectorAll("#promo [data-piece]")) {
    btn.addEventListener("click", () => {
      const pending = ui.pendingPromo;
      ui.pendingPromo = null;
      $("#promo").classList.add("hidden");
      if (pending) sendMove(pending.base + btn.dataset.piece);
    });
  }
  $("#promo-cancel").addEventListener("click", () => {
    ui.pendingPromo = null;
    $("#promo").classList.add("hidden");
    if (ui.state) render(ui.state);
  });
}

// ---------------------------------------------------------------- 控制
async function control(payload) {
  try {
    const res = await fetch("/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await res.json();
    if (!res.ok) {
      toast(body.error || "控制失败", "bad");
      return null;
    }
    if (body.state) render(body.state);
    return body;
  } catch (err) {
    toast("网络错误：" + err.message, "bad");
    return null;
  }
}

async function setMode(mode) {
  const players =
    mode === "hva"
      ? { white: "human", black: "builtin:greedy" }
      : { white: "builtin:greedy", black: "builtin:random" };
  hideOver();
  await control({ action: "new", ...players });
}

function showOver(st) {
  const result = st.result;
  $("#over-title").textContent =
    result === "1/2-1/2" ? "和棋" : result === "1-0" ? "白方胜" : "黑方胜";
  $("#over-sub").textContent = REASON_TEXT[st.over_reason] || st.over_reason || "";
  $("#over").classList.remove("hidden");
}

function hideOver() {
  $("#over").classList.add("hidden");
}

function bindUi() {
  $("#btn-new").addEventListener("click", () => {
    hideOver();
    control({ action: "new" });
  });
  $("#btn-undo").addEventListener("click", () => control({ action: "undo" }));
  $("#btn-resign").addEventListener("click", () => control({ action: "resign" }));
  $("#btn-flip").addEventListener("click", () => {
    ui.orientation = ui.orientation === "white" ? "black" : "white";
    if (ui.state) render(ui.state);
  });
  $("#btn-pgn").addEventListener("click", async () => {
    const text = await (await fetch("/pgn")).text();
    const blob = new Blob([text], { type: "application/x-chess-pgn" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `chessarena-${(ui.state && ui.state.game_id) || "game"}.pgn`;
    a.click();
    URL.revokeObjectURL(a.href);
    toast("PGN 已下载", "good");
  });
  $("#btn-fen").addEventListener("click", async () => {
    if (!ui.state) return;
    try {
      await navigator.clipboard.writeText(ui.state.fen);
      toast("FEN 已复制", "good");
    } catch {
      toast(ui.state.fen, "");
    }
  });
  $("#btn-again").addEventListener("click", () => {
    hideOver();
    control({ action: "new" });
  });
  for (const btn of document.querySelectorAll("#modes button")) {
    btn.addEventListener("click", () => setMode(btn.dataset.mode));
  }
  for (const btn of document.querySelectorAll("#speed-group button[data-speed]")) {
    btn.addEventListener("click", () =>
      control({ action: "speed", speed: Number(btn.dataset.speed) })
    );
  }
  $("#btn-pause").addEventListener("click", () => {
    const paused = ui.state && ui.state.paused;
    control({ action: paused ? "resume" : "pause" });
  });
  $("#btn-step").addEventListener("click", () => control({ action: "step" }));
}

// ---------------------------------------------------------------- WebSocket
function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  ui.ws = ws;

  ws.onopen = () => {
    setConn(true);
    ws.send(JSON.stringify({ type: "ping" }));
  };
  ws.onclose = () => {
    setConn(false);
    setTimeout(connect, 1200);
  };
  ws.onerror = () => setConn(false);
  ws.onmessage = (event) => {
    let msg;
    try {
      msg = JSON.parse(event.data);
    } catch {
      return;
    }
    switch (msg.type) {
      case "hello":
        if (msg.version) $("#version").textContent = " v" + msg.version;
        render(msg.state);
        break;
      case "move":
      case "control":
      case "reset":
        render(msg.state);
        break;
      case "game_over":
        render(msg.state);
        break;
      case "illegal":
      case "retry":
        break;
      default:
        break;
    }
  };
}

function keepAlive() {
  setInterval(() => {
    if (ui.ws && ui.ws.readyState === WebSocket.OPEN) {
      ui.ws.send(JSON.stringify({ type: "ping" }));
    }
  }, 25000);
}

// ---------------------------------------------------------------- 启动
ui.ground = Chessground($("#board"), {
  fen: START_FEN,
  orientation: "white",
  coordinates: true,
  animation: { enabled: true, duration: 180 },
  highlight: { lastMove: true, check: true },
  draggable: { enabled: true, showGhost: true },
  selectable: { enabled: true },
  movable: { free: false, showDests: true, color: undefined, dests: new Map() },
  events: { move: onUserMove },
});

bindUi();
bindPromo();
connect();
keepAlive();
