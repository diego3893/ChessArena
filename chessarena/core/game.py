"""``Game``：裁判。唯一真相源，唯一写入口。

一切落子——AI 提交的、人类点击的、UCI 引擎回答的——最终都进 ``Game.submit()``，
过校验才生效；失败**原子回滚**（局面 / 轮次 / 时钟 / 历史一个都不动）。
"""

import contextlib
import contextvars
import io
import math
import random
import threading
import time
from datetime import datetime
from dataclasses import dataclass, field
from functools import wraps
from uuid import uuid4

import chess
import chess.pgn

from .board import Board
from .player import Player
from .errors import (
    ChessArenaTimeout,
    GameOverError,
    IllegalMoveError,
    NotYourTurnError,
    TransientError,
)
from .moves import parse_uci
from .result import Result
from .rc import RC
from .state import State

START_FEN = chess.STARTING_FEN

#: 当前"谁在落子"的上下文。平台在驱动某一方时设置它，``submit`` 据此判断是否 ``-3``。
_side_ctx = contextvars.ContextVar("chessarena_side", default=None)
_request_ctx = contextvars.ContextVar("chessarena_request", default=None)


@dataclass
class _TurnRequest:
    game: object
    generation: int
    deadline: float
    retry_budget: int
    failures: int = 0
    accepted: Result | None = None
    cancelled: threading.Event = field(default_factory=threading.Event)
    done: threading.Event = field(default_factory=threading.Event)


def _locked(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return call

#: 对外支持的事件名（《API总表》§8）
EVENTS = ("move", "illegal", "opponent_move", "game_over", "timeout", "retry")

#: 终局原因的人话
REASON_TEXT = {
    "checkmate": "将杀",
    "stalemate": "逼和",
    "threefold": "三次重复",
    "fifty": "50 步规则",
    "insufficient": "子力不足",
    "resign": "认输",
    "timeout": "超时",
    "retry_exhausted": "重试次数用尽",
    "forfeit": "弃权",
    "error": "程序异常",
}

_PIECE_NAMES = {
    "P": "兵", "N": "马", "B": "象", "R": "车", "Q": "后", "K": "王",
    "p": "兵", "n": "马", "b": "象", "r": "车", "q": "后", "k": "王",
}
_SIDE_TEXT = {"w": "白方", "b": "黑方"}


class Game:
    """一局棋的裁判。"""

    def __init__(
        self,
        white,
        black,
        *,
        fen=None,
        timeout=3.0,
        max_retries=3,
        on_retry_exhausted="forfeit",
        on_timeout="forfeit",
        game_id=None,
        live=False,
        record=False,
        seed=0,
        logger=None,
    ):
        start = fen or START_FEN
        try:
            self._board = self._validated_board(start)
        except ValueError as exc:
            raise ValueError("起始 FEN 不合法：%r" % (start,)) from exc

        self.white = white
        self.black = black
        self.start_fen = start
        self.game_id = game_id or self._make_id()
        self.live = live
        self.record = record
        self.timeout = float(timeout)
        self.max_retries = int(max_retries)
        if not math.isfinite(self.timeout) or self.timeout <= 0:
            raise ValueError("timeout须为有限正数")
        if self.max_retries < 0:
            raise ValueError("max_retries不能为负数")
        if on_retry_exhausted not in ("forfeit", "random"):
            raise ValueError("on_retry_exhausted 只能是 forfeit / random")
        if on_timeout not in ("forfeit", "random"):
            raise ValueError("on_timeout 只能是 forfeit / random")
        self.on_retry_exhausted = on_retry_exhausted
        self.on_timeout = on_timeout

        self._history: list[str] = []
        self._last_error: str | None = None
        self._result: str | None = None
        self._over_reason: str | None = None
        self._listeners: dict[str, list] = {name: [] for name in EVENTS}
        self._generation = 0
        self._deadline: float | None = None
        self._logger = logger
        self.rejected: list[dict] = []  # 被拒记录，联赛"非法率"用
        self._rng = random.Random(seed)
        self._lock = threading.RLock()
        self._step_lock = threading.Lock()
        terminal = self._terminal()
        if terminal is not None:
            self._over_reason, self._result = terminal

        for agent, color in ((white, "w"), (black, "b")):
            if agent is None:
                continue
            agent.game = self.player(color)
            agent.color = color
            agent.on_game_start(self.state, color)

    # ------------------------------------------------------------------
    # 只读属性
    # ------------------------------------------------------------------
    @property
    def board(self) -> Board:
        return Board._live(lambda: self.state)

    @property
    def state(self) -> State:
        with self._lock:
            return State(self._board, self._history, self._last_error, result=self._result,
                         start_fen=self.start_fen, game_id=self.game_id,
                         over_reason=self._over_reason, over=self.over)

    def player(self, side):
        """训练和比赛共用的受限选手接口。"""
        if side not in ("w", "b"):
            raise ValueError("side须为w或b")

        def submit(move, *, strict=False):
            with self._lock:
                request = _request_ctx.get()
                if request is not None and self._stale_request(request):
                    if strict:
                        raise NotYourTurnError("该次思考已结束或超时")
                    return Result(RC.NOT_YOUR_TURN, "该次思考已结束或超时", None)
                with self.acting_as(side):
                    result = self.submit(move, strict=strict)
                if request is not None and not result.ok and result.code in (RC.ILLEGAL_MOVE, RC.BAD_FORMAT):
                    request.failures += 1
                    if request.failures > request.retry_budget:
                        request.cancelled.set()
                        request.done.set()
                return result

        def resign():
            with self._lock:
                request = _request_ctx.get()
                if request is not None and self._stale_request(request):
                    return Result(RC.NOT_YOUR_TURN, "该次思考已结束或超时", None)
                return self.resign(side)

        return Player(side, lambda: self.state, submit, resign, lambda: self.clock(side))

    def _stale_request(self, request):
        return (request.game is not self or request.generation != self._generation or
                request.cancelled.is_set() or time.monotonic() >= request.deadline)

    @staticmethod
    def _validated_board(fen):
        if not isinstance(fen, str):
            raise ValueError("FEN须为字符串")
        board = chess.Board(fen)
        if not board.is_valid():
            raise ValueError("FEN局面无效：%s" % fen)
        return board

    @property
    def turn(self) -> str:
        return "w" if self._board.turn else "b"

    @property
    def over(self) -> bool:
        return self._result is not None

    @property
    def result(self) -> str | None:
        return self._result

    @property
    def over_reason(self) -> str | None:
        return self._over_reason

    @property
    def history(self) -> tuple[str, ...]:
        return tuple(self._history)

    @property
    def ply(self) -> int:
        return len(self._history)

    @property
    def last_error(self) -> str | None:
        return self._last_error

    # ------------------------------------------------------------------
    # 唯一写入口
    # ------------------------------------------------------------------
    def submit(self, move, *, strict=False) -> Result:
        """落子。``strict=True`` 时把失败返回码转成异常。"""
        with self._lock:
            result = self._submit(move)
        if strict and not result.ok:
            raise self._as_exception(result)
        return result

    @contextlib.contextmanager
    def acting_as(self, side):
        """把当前调用方标记为某一方（平台驱动 AI 时用，测试也用它）。"""
        token = _side_ctx.set(side)
        try:
            yield
        finally:
            _side_ctx.reset(token)

    def _submit(self, move) -> Result:
        if self.over:
            return self._reject(
                RC.GAME_OVER, "对局已结束（%s），不能再落子" % self._reason_text(), move
            )

        parsed = parse_uci(move)
        if parsed is None:
            return self._reject(
                RC.BAD_FORMAT,
                "着法格式不对：%r（要写成 e2e4 这样的小写起终点，升变加 q/r/b/n）" % (move,),
                move,
            )

        side = _side_ctx.get()
        if side is not None and side != self.turn:
            return self._reject(
                RC.NOT_YOUR_TURN,
                "还没轮到你：现在是%s走（你是%s）" % (_SIDE_TEXT[self.turn], _SIDE_TEXT[side]),
                move,
            )

        from_sq, to_sq, promo = parsed
        candidate = chess.Move.from_uci(from_sq + to_sq + promo)
        if candidate not in self._board.legal_moves:
            return self._reject(RC.ILLEGAL_MOVE, self._illegal_reason(from_sq, to_sq), move)

        mover = self.turn
        self._board.push(candidate)
        played = candidate.uci()
        self._history.append(played)
        self._last_error = None
        self._generation += 1
        self._deadline = None

        result = Result(RC.OK, "落子成功：%s" % played, played)
        request = _request_ctx.get()
        if request is not None and request.game is self:
            request.accepted = result
        self._emit("move", played, result)
        other = self.black if mover == "w" else self.white
        if other is not None:
            self._notify(other, "on_opponent_move", played)

        terminal = self._terminal()
        if terminal is not None:
            reason, outcome = terminal
            self._finish(outcome, reason)
        if request is not None and request.game is self:
            request.done.set()
        return result

    @_locked
    def resign(self, side=None) -> Result:
        """认输；缺省为当前走子方。"""
        if self.over:
            return Result(RC.GAME_OVER, "对局已结束", None)
        side = side or _side_ctx.get() or self.turn
        if side not in ("w", "b"):
            return Result(RC.BAD_FORMAT, "side须为w或b", None)
        loser_is_white = side == "w"
        self._finish("0-1" if loser_is_white else "1-0", "resign")
        return Result(RC.OK, "%s认输" % _SIDE_TEXT[side], None)

    @_locked
    def undo(self, n=1) -> bool:
        """回退 ``n`` 个半步；成功返回 True。"""
        if not isinstance(n, int) or n < 1 or not self._history:
            return False
        if self.over:
            self._result = None
            self._over_reason = None
        done = 0
        while done < n and self._history:
            self._board.pop()
            self._history.pop()
            done += 1
        if done:
            self._last_error = None
            self._deadline = None
            self._generation += 1
        return done > 0

    @_locked
    def reset(self, fen=None):
        """清空历史，回到指定局面。"""
        start = fen or self.start_fen
        board = self._validated_board(start)
        self._board = board
        self.start_fen = start
        self._history.clear()
        self.rejected.clear()
        self._last_error = None
        self._result = None
        self._over_reason = None
        self._deadline = None
        self._generation += 1
        terminal = self._terminal()
        if terminal is not None:
            self._over_reason, self._result = terminal

    # ------------------------------------------------------------------
    # 驱动：单步 / 跑到结束
    # ------------------------------------------------------------------
    def step(self) -> Result:
        """让当前走子方走一步（观战"单步"用）。"""
        with self._step_lock:
            if self.over:
                return Result(RC.GAME_OVER, "对局已结束（%s）" % self._reason_text(), None)
            side = self.turn
            agent = self.white if side == "w" else self.black
            if agent is None or getattr(agent, "is_api", False):
                return Result(RC.NOT_YOUR_TURN, "%s等待外部提交" % _SIDE_TEXT[side], None)
            return self._play_turn(side, agent)

    def run_to_end(self, *, max_plies=1000) -> str | None:
        """自动驱动双方到终局，返回 ``result``。"""
        while not self.over and self.ply < max_plies:
            result = self.step()
            if result.code == RC.NOT_YOUR_TURN:
                break
        return self.result

    def wait_my_turn(self, *, timeout=10.0) -> bool:
        """阻塞到轮到自己（或对局结束 / 超时）。"""
        side = _side_ctx.get() or self.turn
        end = time.monotonic() + float(timeout)
        while not self.over and self.turn != side:
            if time.monotonic() >= end:
                return False
            time.sleep(0.005)
        return self.turn == side and not self.over

    def clock(self, side=None) -> float:
        """当前这一步还剩多少秒预算（不在该方回合 / 已结束则为 0.0）。"""
        if self.over:
            return 0.0
        side = side or self.turn
        if side != self.turn:
            return 0.0
        if self._deadline is None:
            return self.timeout
        return max(0.0, self._deadline - time.monotonic())

    # ------------------------------------------------------------------
    # 事件
    # ------------------------------------------------------------------
    def on(self, event, callback):
        """订阅事件（``move`` / ``illegal`` / ``opponent_move`` / ``game_over`` / ``timeout`` / ``retry``）。"""
        if event not in self._listeners:
            raise ValueError("未知事件：%r（可用：%s）" % (event, ", ".join(EVENTS)))
        self._listeners[event].append(callback)

    def _emit(self, event, *args):
        for callback in list(self._listeners.get(event, ())):
            try:
                callback(*args)
            except Exception as exc:  # 监听者出错不能拖垮对局
                self._log("event %s 回调异常：%r" % (event, exc))

    # ------------------------------------------------------------------
    # 导出
    # ------------------------------------------------------------------
    @_locked
    def pgn(self) -> str:
        """导出 PGN（含双方名字与结果）。"""
        game = chess.pgn.Game()
        game.headers["Event"] = "ChessArena"
        game.headers["Site"] = "local"
        game.headers["Date"] = datetime.now().strftime("%Y.%m.%d")
        game.headers["Round"] = "-"
        game.headers["White"] = getattr(self.white, "name", "?") or "?"
        game.headers["Black"] = getattr(self.black, "name", "?") or "?"
        game.headers["Result"] = self._result or "*"
        game.headers["GameId"] = self.game_id
        if self.start_fen != START_FEN:
            game.setup(self.start_fen)
        node = game
        for uci_move in self._history:
            node = node.add_variation(chess.Move.from_uci(uci_move))
        out = io.StringIO()
        print(game, file=out)
        return out.getvalue()

    @_locked
    def to_json(self) -> dict:
        state = self.state
        payload = state.to_json()
        payload.update({
            "game_id": self.game_id,
            "start_fen": self.start_fen,
            "fen": state.fen,
            "turn": state.turn,
            "ply": state.ply,
            "history": list(state.history),
            "history_san": self._san_history(),
            "captured": self._captured(),
            "last_move": self._history[-1] if self._history else None,
            "is_check": state.is_check,
            "over": self.over,
            "result": self.result,
            "over_reason": self.over_reason,
            "last_error": state.last_error,
            "white": getattr(self.white, "name", None),
            "black": getattr(self.black, "name", None),
        })
        return payload

    def _san_history(self) -> list[str]:
        """把走过的着法翻成 SAN（前端记谱用，避免在 JS 里重写规则）。"""
        board = chess.Board(self.start_fen)
        out: list[str] = []
        for uci_move in self._history:
            move = chess.Move.from_uci(uci_move)
            try:
                out.append(board.san(move))
            except ValueError:  # 理论上不会发生；宁可有缺口也不要 500
                out.append(uci_move)
            board.push(move)
        return out

    def _captured(self) -> dict:
        """双方各吃了哪些子：``{"w": ["p", ...], "b": [...]}``（存被吃方的符号）。"""
        board = chess.Board(self.start_fen)
        out = {"w": [], "b": []}
        for uci_move in self._history:
            move = chess.Move.from_uci(uci_move)
            if board.is_capture(move):
                if board.is_en_passant(move):
                    square = chess.square(
                        chess.square_file(move.to_square), chess.square_rank(move.from_square)
                    )
                else:
                    square = move.to_square
                victim = board.piece_at(square)
                if victim is not None:
                    out["w" if victim.color else "b"].append(victim.symbol())
            board.push(move)
        return out

    # ------------------------------------------------------------------
    # 内部：驱动一方
    # ------------------------------------------------------------------
    def _play_turn(self, side, agent) -> Result:
        deadline = time.monotonic() + self.timeout
        self._deadline = deadline
        attempts = 0
        while True:
            with self._lock:
                if self.over:
                    return Result(RC.GAME_OVER, "对局已结束", None)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return self._dispose(side, "timeout")
                request = _TurnRequest(self, self._generation, deadline,
                                       self.max_retries-attempts)
            error = None
            move = None
            try:
                move = self._ask(agent, side, remaining, request)
            except Exception as exc:
                error = exc

            with self._lock:
                # 已接受的动作不因选手返回慢或后续异常而被重复执行/误判负。
                if request.accepted is not None:
                    return request.accepted
                if self.over:
                    return Result(RC.GAME_OVER, "对局已结束", None)
                if request.generation != self._generation:
                    return Result(RC.NOT_YOUR_TURN, "思考期间对局已变更", None)
                if request.failures > request.retry_budget:
                    return self._dispose(side, "retry_exhausted")
                if time.monotonic() >= deadline:
                    return self._dispose(side, "timeout")
                if isinstance(error, ChessArenaTimeout):
                    return self._dispose(side, "timeout")
                if isinstance(error, TransientError):
                    attempts += request.failures+1
                    self._emit("retry", side, attempts, Result(RC.ILLEGAL_MOVE, str(error), None))
                    if attempts > self.max_retries:
                        return self._dispose(side, "retry_exhausted", detail=str(error))
                    continue
                if error is not None:
                    self._log("%s思考时抛异常：%r" % (_SIDE_TEXT[side], error))
                    return self._dispose(side, "error", detail=repr(error))
                if move is None:
                    return self._dispose(side, "forfeit")
                result = move if isinstance(move, Result) and not move.ok else self.submit(move)
                if result.ok or result.code == RC.GAME_OVER:
                    return result
                if getattr(agent, "is_human", False):
                    continue
                attempts += max(1, request.failures)
                self._emit("retry", side, attempts, result)
                if attempts > self.max_retries:
                    return self._dispose(side, "retry_exhausted")

    def _ask(self, agent, side, seconds, request):
        """等待选手返回或已接受的主动提交；取消过期请求。"""
        state = self.state
        if getattr(agent, "fast_local", False):
            token = _side_ctx.set(side)
            request_token = _request_ctx.set(request)
            started = time.monotonic()
            try:
                move = agent.choose_move(state)
            finally:
                request.cancelled.set()
                _request_ctx.reset(request_token)
                _side_ctx.reset(token)
            if time.monotonic() - started > seconds:
                raise ChessArenaTimeout("思考超时")
            return move

        ctx = contextvars.copy_context()
        box: dict = {}

        def run():
            _side_ctx.set(side)
            _request_ctx.set(request)
            try:
                box["move"] = agent.choose_move(state)
            except BaseException as exc:
                box["error"] = exc if isinstance(exc, Exception) else RuntimeError(repr(exc))
            finally:
                request.done.set()

        thread = threading.Thread(target=ctx.run, args=(run,), daemon=True, name="chessarena-agent")
        thread.start()
        finished = request.done.wait(seconds)
        request.cancelled.set()
        if not finished and request.accepted is None:
            raise ChessArenaTimeout("思考超时（%.2fs未返回）" % seconds)
        if "error" in box:
            raise box["error"]
        return box.get("move")

    def _dispose(self, side, reason, detail=None):
        """处置当前走子方：按配置替走一步，或直接判负。"""
        if reason == "timeout":
            policy = self.on_timeout
            self._emit("timeout", side, self.timeout)
        elif reason == "retry_exhausted":
            policy = self.on_retry_exhausted
        else:  # error / forfeit：没有"替走一步"的语义，直接判负
            policy = "forfeit"
        if policy == "random":
            legal = sorted(m.uci() for m in self._board.legal_moves)
            if legal:
                substitute = self._rng.choice(legal)
                result = self.submit(substitute)
                if result.ok:
                    self._log("%s%s，随机替走 %s" % (_SIDE_TEXT[side], reasoning_cn(reason), substitute))
                    return result
        text = "%s%s，判负" % (_SIDE_TEXT[side], reasoning_cn(reason))
        if detail:
            text += "（%s）" % (detail,)
        self._log(text)
        self._finish("0-1" if side == "w" else "1-0", reason)
        return Result(RC.GAME_OVER, text, None)

    def _notify(self, agent, method, *args):
        try:
            getattr(agent, method)(*args)
        except (Exception, SystemExit) as exc:
            self._log("%s回调异常：%r" % (method, exc))

    @_locked
    def _finish(self, outcome, reason):
        if self.over:
            return
        self._result = outcome
        self._over_reason = reason
        self._generation += 1
        self._deadline = None
        self._emit("game_over", outcome, reason)
        for agent in (self.white, self.black):
            if agent is not None:
                self._notify(agent, "on_game_end", outcome)
        request = _request_ctx.get()
        if request is not None and request.game is self:
            request.done.set()

    def _terminal(self):
        """检查终局；返回 ``(reason, result)`` 或 ``None``。"""
        board = self._board
        if board.is_checkmate():
            return "checkmate", "0-1" if board.turn else "1-0"
        if board.is_stalemate():
            return "stalemate", "1/2-1/2"
        if board.is_insufficient_material():
            return "insufficient", "1/2-1/2"
        if board.is_repetition(3) or board.is_fivefold_repetition():
            return "threefold", "1/2-1/2"
        if board.is_seventyfive_moves() or board.is_fifty_moves():
            return "fifty", "1/2-1/2"
        return None

    # ------------------------------------------------------------------
    # 内部：失败原因
    # ------------------------------------------------------------------
    def _reject(self, code, reason, move=None) -> Result:
        self._last_error = reason
        result = Result(code, reason, None)
        if code in (RC.ILLEGAL_MOVE, RC.BAD_FORMAT):
            self.rejected.append({"ply": self.ply, "side": self.turn, "code": code, "reason": reason})
        self._emit("illegal", move, result)
        return result

    def _illegal_reason(self, from_sq, to_sq) -> str:
        piece = self._board.piece_at(chess.parse_square(from_sq))
        if piece is None:
            return "非法着法：%s 上没有棋子" % (from_sq,)
        owner = "白方" if piece.color else "黑方"
        if (piece.color and self.turn == "b") or (not piece.color and self.turn == "w"):
            return "非法着法：%s 是%s的%s，现在轮到%s走" % (
                from_sq, owner, _PIECE_NAMES[piece.symbol()], _SIDE_TEXT[self.turn]
            )
        return "非法着法：%s到%s不符合走子规则或会使己方王受将" % (from_sq, to_sq)

    def _as_exception(self, result):
        if result.code in (RC.ILLEGAL_MOVE, RC.BAD_FORMAT):
            return IllegalMoveError(result.reason)
        if result.code == RC.NOT_YOUR_TURN:
            return NotYourTurnError(result.reason)
        return GameOverError(result.reason)

    def _reason_text(self):
        return REASON_TEXT.get(self._over_reason or "", self._over_reason or "未知")

    def _log(self, message):
        if self._logger is not None:
            self._logger(message)

    @staticmethod
    def _make_id():
        return datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid4().hex[:12]


def reasoning_cn(reason):
    """终局原因的简短中文（用于日志）。"""
    return REASON_TEXT.get(reason, reason)
