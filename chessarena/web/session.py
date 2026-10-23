"""``Session``：一局棋 + 一个后台驱动线程 + 一个广播总线。

- 人类一方：等 HTTP ``POST /move``；
- AI 一方：由驱动线程按 ``speed`` 自动走；
- 每条事件都推给 `/ws` 的连接（页面），协议见《API总表》§16.3。
"""

import sys
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

    def __init__(self, arena, white, black, *, fen=None, speed=1.0, heartbeat=3.0):
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
        self._steps = 0
        self._stalls = 0
        self._last_error = None
        self._revision = 0
        self._heartbeat = float(heartbeat)
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

    @property
    def heartbeat(self) -> float:
        return self._heartbeat

    @property
    def driver_alive(self) -> bool:
        return self._driver.is_alive()

    def ensure_driver(self):
        """驱动线程意外退出时重启它（自愈）。返回是否重启过。"""
        if self._stop or self._driver.is_alive():
            return False
        self._log("驱动线程已退出，重启中")
        self._driver = threading.Thread(target=self._drive, daemon=True, name="chessarena-driver")
        self._driver.start()
        return True

    def debug(self) -> dict:
        with self._lock:
            game = self._game
            return {
                "game_id": game.game_id,
                "ply": game.ply,
                "turn": game.turn,
                "over": game.over,
                "paused": self._paused,
                "speed": self._speed,
                "driver_alive": self._driver.is_alive(),
                "steps": self._steps,
                "stalls": self._stalls,
                "last_error": self._last_error,
                "clients": len(self.hub._queues),
            }

    def _log(self, message):
        print("[chessarena] %s" % (message,), file=sys.stderr, flush=True)

    def snapshot(self) -> dict:
        with self._lock:
            return self._snapshot_unlocked()

    def _snapshot_unlocked(self) -> dict:
        """会话锁已由调用方或等待学生线程的驱动持有时使用。"""
        payload = self._game.to_json()
        payload["human"] = {"w": self._is_human("w"), "b": self._is_human("b")}
        payload["api"] = {"w": self._is_api("w"), "b": self._is_api("b")}
        payload["players"] = {"w": self._spec_text(self.white_spec),
                              "b": self._spec_text(self.black_spec)}
        payload["paused"] = self._paused
        payload["speed"] = self._speed
        payload["timeout"] = self.arena.timeout
        payload["revision"] = self._revision
        return payload

    @staticmethod
    def _spec_text(spec):
        """把选手写法统一成前端能回填的字符串。"""
        if isinstance(spec, str):
            return spec
        if spec is None:
            return "none"
        if getattr(spec, "is_human", False):
            return "human"
        return "agent:%s" % (getattr(spec, "name", type(spec).__name__),)

    def players(self) -> dict:
        with self._lock:
            return {"w": self._spec_text(self.white_spec),
                    "b": self._spec_text(self.black_spec)}

    def available_players(self) -> dict:
        """给页面下拉框用：可选的人类 / 内置档 / 已加载的 agents。"""
        agents = [
            {"name": info.name, "path": info.path, "spec": info.spec}
            for info in (self.arena.agents() or [])
        ]
        return {"human": True, "api": True, "builtin": self.arena.builtins(), "agents": agents}

    # ------------------------------------------------------------------
    def submit(self, move, *, side=None) -> Result:
        """人类/API提交提案；执棋颜色和走子权均由服务端检查。"""
        with self._lock:
            game = self._game
            if game.over:
                return Result(RC.GAME_OVER, "对局已结束（%s）" % (game.over_reason,), None)
            if side is not None and side not in ("w", "b"):
                return Result(RC.BAD_FORMAT, "side须为w或b", None)
            if side is not None and side != game.turn:
                return Result(RC.NOT_YOUR_TURN, "还没轮到你走棋", None)
            turn = game.turn
            if self._is_api(turn) and side is None:
                return Result(RC.NOT_YOUR_TURN, "API选手提交时必须指定side（w或b）", None)
            if not self._is_human(turn) and not self._is_api(turn):
                return Result(
                    RC.NOT_YOUR_TURN,
                    "现在是 AI 回合（%s），等它走" % ("白方" if turn == "w" else "黑方",),
                    None,
                )
            if self._paused:
                return Result(RC.NOT_YOUR_TURN, "对局已暂停", None)
            with game.acting_as(turn):
                return game.submit(move)

    def reset(self, fen=None) -> Result:
        with self._lock:
            game = self._game
            try:
                game.reset(fen or self.fen)
            except ValueError as exc:
                return Result(RC.BAD_FORMAT, "起始 FEN 不合法：%s" % (exc,), None)
            self._paused = False
            self._revision += 1
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
                if not game.over and not self._is_manual(game.turn):
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
                try:
                    self._build_game(white, black)
                except Exception as exc:  # 选手写法错误 → 400，且对局保持原样
                    raise ValueError("开局失败：%s" % (exc,)) from exc
                self._paused = False
            else:
                raise ValueError("未知动作：%r（可用 pause/resume/step/speed/undo/resign/new）" % (action,))
            self._revision += 1
            state = self.snapshot()
            message = {"type": "control", "paused": self._paused, "speed": self._speed, "state": state}
            self.hub.push(message)
            return message

    def stop(self):
        self._stop = True
        if self._driver.is_alive():
            self._driver.join(timeout=2.0)

    # ------------------------------------------------------------------
    def _build_game(self, white=None, black=None):
        """先按新选手建好对局，成功了才替换旧的（失败时原局不受影响）。"""
        white = white or self.white_spec
        black = black or self.black_spec
        game = self.arena.new_game(white=white, black=black, fen=self.fen)
        old = getattr(self, "_game", None)
        if old is not None:
            for agent in (old.white, old.black):
                if agent is not None and not getattr(agent, "is_human", False):
                    try:
                        agent.close()
                    except Exception:
                        pass
        game.on("move", self._on_move)
        game.on("illegal", self._on_illegal)
        game.on("game_over", self._on_game_over)
        game.on("retry", self._on_retry)
        self._game = game
        self.white_spec = white
        self.black_spec = black
        return game

    def _is_human(self, side) -> bool:
        game = self._game
        agent = game.white if side == "w" else game.black
        return bool(getattr(agent, "is_human", False))

    def _is_api(self, side) -> bool:
        agent = self._game.white if side == "w" else self._game.black
        return bool(getattr(agent, "is_api", False))

    def _is_manual(self, side) -> bool:
        return self._is_human(side) or self._is_api(side)

    # --- 事件 → 广播 ---------------------------------------------------
    def _on_move(self, move, result):
        self._revision += 1
        # 学生线程submit时，驱动正持会话锁等待其返回；回调不能再次取锁。
        self.hub.push({"type": "move", "move": move, "ply": self._game.ply,
                       "state": self._snapshot_unlocked()})

    def _on_illegal(self, move, result):
        self.hub.push({"type": "illegal", "move": move, "code": result.code,
                       "reason": result.reason})

    def _on_game_over(self, result, reason):
        self._revision += 1
        self.hub.push({"type": "game_over", "result": result, "reason": reason,
                       "state": self._snapshot_unlocked()})

    def _on_retry(self, side, attempt, result):
        self.hub.push({"type": "retry", "side": side, "attempt": attempt,
                       "code": result.code, "reason": result.reason})

    # --- AI 驱动 -------------------------------------------------------
    def _drive(self):
        while not self._stop:
            try:
                idle = True
                with self._lock:
                    if self._stop:
                        return
                    game = self._game
                    if not self._paused and not game.over and not self._is_manual(game.turn):
                        before = game.ply
                        game.step()
                        progressed = game.ply != before or game.over
                        if progressed:
                            self._steps += 1
                            self._stalls = 0
                        else:
                            # 没有推进（例如该方没绑定 AI）：别空转，记下来
                            self._stalls += 1
                            if self._stalls in (1, 5, 20):
                                self._log(
                                    "AI 步未推进（第 %d 次）：turn=%s over=%s"
                                    % (self._stalls, game.turn, game.over)
                                )
                        idle = not progressed
                if idle:
                    time.sleep(0.05)
                else:
                    time.sleep(self._base_delay / max(0.05, self._speed))
            except Exception as exc:  # 驱动线程绝不能静默死掉
                self._last_error = repr(exc)
                self._log("驱动异常：%r" % (exc,))
                time.sleep(0.5)

