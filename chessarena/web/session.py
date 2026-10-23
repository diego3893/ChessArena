"""``Session``：一局棋 + 一个后台驱动线程 + 一个广播总线。

- 人类一方：等 HTTP ``POST /move``；
- AI 一方：由驱动线程按 ``speed`` 自动走；
- 每条事件都推给 `/ws` 的连接（页面），协议见《API总表》§16.3。
"""

import threading
import time

from ..core.result import Result
from ..core.rc import RC


class Hub:
    """把消息从任意线程安全地送到所有 WebSocket 连接。"""

    def __init__(self, loop=None):
        self.loop = loop
        self._queues = set()
        self._lock = threading.Lock()

    def register(self, queue):
        with self._lock:
            self._queues.add(queue)
        return queue

    def unregister(self, queue):
        with self._lock:
            self._queues.discard(queue)

    def push(self, message):
        loop = self.loop
        if loop is None:
            return
        with self._lock:
            queues = list(self._queues)
        for queue in queues:
            try:
                loop.call_soon_threadsafe(queue.put_nowait, message)
            except RuntimeError:  # 事件循环已关闭
                self.unregister(queue)


class Session:
    """一局棋的服务端会话。"""

    def __init__(self, arena, white, black, *, fen=None, speed=1.0):
        self.arena = arena
        self.white_spec = white
        self.black_spec = black
        self.fen = fen
        self.hub = Hub()
        self._lock = threading.RLock()
        self._paused = False
        self._speed = float(speed)
        self._base_delay = 0.35  # 1× 速度下 AI 每步间隔，给页面看清楚
        self._stop = False
        self._game = None
        self._build_game()
        self._driver = threading.Thread(
            target=self._drive, daemon=True, name="chessarena-driver"
        )
        self._driver.start()

    # ------------------------------------------------------------------
    @property
    def game(self):
        with self._lock:
            return self._game

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def speed(self) -> float:
        return self._speed

    def snapshot(self) -> dict:
        with self._lock:
            payload = self._game.to_json()
            payload["human"] = {"w": self._is_human("w"), "b": self._is_human("b")}
            payload["paused"] = self._paused
            payload["speed"] = self._speed
            payload["timeout"] = self.arena.timeout
            return payload

    # ------------------------------------------------------------------
    def submit(self, move) -> Result:
        """人类落子；轮到 AI 时返回 ``-3``。"""
        with self._lock:
            game = self._game
            if game.over:
                return Result(RC.GAME_OVER, "对局已结束（%s）" % (game.over_reason,), None)
            side = game.turn
            if not self._is_human(side):
                return Result(
                    RC.NOT_YOUR_TURN,
                    "现在是 AI 回合（%s），等它走" % ("白方" if side == "w" else "黑方",),
                    None,
                )
            with game.acting_as(side):
                return game.submit(move)

    def reset(self, fen=None) -> Result:
        with self._lock:
            game = self._game
            try:
                game.reset(fen or self.fen)
            except ValueError as exc:
                return Result(RC.BAD_FORMAT, "起始 FEN 不合法：%s" % (exc,), None)
            self._paused = False
            self.hub.push({"type": "reset", "state": self.snapshot()})
            return Result(RC.OK, "已重开", None)

    def control(self, action, speed=None, white=None, black=None):
        """暂停 / 继续 / 单步 / 调速 / 悔棋 / 认输 / 开新局。"""
        with self._lock:
            game = self._game
            if action == "pause":
                self._paused = True
            elif action == "resume":
                self._paused = False
            elif action == "speed":
                if speed is not None:
                    self._speed = max(0.05, float(speed))
            elif action == "step":
                if not game.over and not self._is_human(game.turn):
                    game.step()
            elif action == "undo":
                # 退到人类回合：人机模式一步悔棋 = 退两步（自己 + AI 应手）
                human = [side for side in ("w", "b") if self._is_human(side)]
                if len(human) == 1:
                    plies = 2 if game.turn == human[0] else 1
                else:
                    plies = 1
                game.undo(plies)
            elif action == "resign":
                human = [side for side in ("w", "b") if self._is_human(side)]
                game.resign(human[0] if len(human) == 1 else game.turn)
            elif action == "new":
                if white:
                    self.white_spec = white
                if black:
                    self.black_spec = black
                self._build_game()
                self._paused = False
            else:
                raise ValueError("未知动作：%r（可用 pause/resume/step/speed/undo/resign/new）" % (action,))
            state = self.snapshot()
            message = {"type": "control", "paused": self._paused, "speed": self._speed, "state": state}
            self.hub.push(message)
            return message

    def stop(self):
        self._stop = True
        if self._driver.is_alive():
            self._driver.join(timeout=2.0)

    # ------------------------------------------------------------------
    def _build_game(self):
        old = getattr(self, "_game", None)
        if old is not None:
            for agent in (old.white, old.black):
                if agent is not None and not getattr(agent, "is_human", False):
                    try:
                        agent.close()
                    except Exception:
                        pass
        game = self.arena.new_game(white=self.white_spec, black=self.black_spec, fen=self.fen)
        game.on("move", self._on_move)
        game.on("illegal", self._on_illegal)
        game.on("game_over", self._on_game_over)
        game.on("retry", self._on_retry)
        self._game = game
        return game

    def _is_human(self, side) -> bool:
        game = self._game
        agent = game.white if side == "w" else game.black
        return bool(getattr(agent, "is_human", False))

    # --- 事件 → 广播 ---------------------------------------------------
    def _on_move(self, move, result):
        self.hub.push({"type": "move", "move": move, "ply": self._game.ply,
                       "state": self.snapshot()})

    def _on_illegal(self, move, result):
        self.hub.push({"type": "illegal", "move": move, "code": result.code,
                       "reason": result.reason})

    def _on_game_over(self, result, reason):
        self.hub.push({"type": "game_over", "result": result, "reason": reason,
                       "state": self.snapshot()})

    def _on_retry(self, side, attempt, result):
        self.hub.push({"type": "retry", "side": side, "attempt": attempt,
                       "code": result.code, "reason": result.reason})

    # --- AI 驱动 -------------------------------------------------------
    def _drive(self):
        while not self._stop:
            idle = True
            with self._lock:
                if self._stop:
                    return
                game = self._game
                if not self._paused and not game.over and not self._is_human(game.turn):
                    game.step()
                    idle = False
            if idle:
                time.sleep(0.05)
            else:
                time.sleep(self._base_delay / self._speed)
