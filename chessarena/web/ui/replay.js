// 回放时钟只移动本地游标，不向实时对局发送控制请求。
export class ReplayPlayer {
  constructor(onChange, timers = globalThis) {
    this.onChange = onChange;
    this.timers = timers;
    this.games = [];
    this.gameIndex = 0;
    this.ply = 0;
    this.speed = 1;
    this.playing = false;
    this.timer = null;
  }
  get game() { return this.games[this.gameIndex] || null; }
  get length() { return this.game ? this.game.moves.length : 0; }
  get frame() { return this.game ? this.game.frames[this.ply] : null; }
  cancel() {
    if (this.timer !== null) this.timers.clearTimeout(this.timer);
    this.timer = null;
  }
  pause(notify = true) {
    this.cancel();
    this.playing = false;
    if (notify) this.onChange();
  }
  load(games) {
    if (!Array.isArray(games) || !games.length) throw new Error("记录中没有对局");
    this.pause(false);
    this.games = games;
    this.gameIndex = this.ply = 0;
    this.onChange();
  }
  selectGame(index) {
    if (!Number.isInteger(index) || !this.games[index]) return;
    this.pause(false);
    this.gameIndex = index;
    this.ply = 0;
    this.onChange();
  }
  seek(ply) {
    if (!Number.isFinite(ply)) return;
    this.pause(false);
    this.ply = Math.max(0, Math.min(this.length, Math.trunc(ply)));
    this.onChange();
  }
  schedule() {
    this.cancel();
    if (!this.playing) return;
    this.timer = this.timers.setTimeout(() => {
      this.timer = null;
      this.ply++;
      if (this.ply >= this.length) this.playing = false;
      this.onChange();
      this.schedule();
    }, 800 / this.speed);
  }
  play() {
    if (!this.length || this.playing) return;
    if (this.ply === this.length) this.ply = 0;
    this.playing = true;
    this.onChange();
    this.schedule();
  }
  toggle() { this.playing ? this.pause() : this.play(); }
  setSpeed(speed) {
    if (![0.5, 1, 2, 4].includes(speed)) return;
    this.speed = speed;
    this.schedule();
    this.onChange();
  }
}

export function replayState(player) {
  const game = player.game;
  if (!game) return null;
  return {
    ...player.frame,
    white: game.headers.White || "白方",
    black: game.headers.Black || "黑方",
    ply: player.ply,
    over: player.ply === player.length,
    result: game.result,
    replayMoves: game.moves,
    start_fen: game.frames[0].fen,
  };
}

// 每条着法自带走棋方和回合编号，兼容黑方先行的自定义FEN。
export function moveRows(moves) {
  const rows = [];
  moves.forEach((move, index) => {
    let row = rows[rows.length - 1];
    if (!row || row.number !== move.fullmove_number) {
      row = { number: move.fullmove_number, w: null, b: null };
      rows.push(row);
    }
    row[move.side] = { san: move.san, ply: index + 1 };
  });
  return rows;
}
