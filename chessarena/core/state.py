"""``State``：给 AI 的不可变快照。

一次拿全所有需要的信息，随便存、随便递归，绝不会影响真实对局。
``apply(move)`` 返回**新** ``State``（不改原对象），学生写 minimax 时不会出现
"忘了撤销"的整类 bug。
"""

import chess

from .errors import IllegalMoveError
from .moves import parse_uci


class State:
    """对局在某一刻的只读快照。"""

    __slots__ = ("_b", "_history", "_last_error", "_matrix", "_legal")

    def __init__(self, board: chess.Board, history=(), last_error=None):
        # ``board`` 只在内部用于派生新快照，从不对外暴露，因此外部无法改写它。
        self._b = board
        self._history = tuple(history)
        self._last_error = last_error
        self._matrix = None
        self._legal = None

    # --- 基本属性 -----------------------------------------------------
    @property
    def fen(self) -> str:
        return self._b.fen()

    @property
    def turn(self) -> str:
        return "w" if self._b.turn else "b"

    @property
    def ply(self) -> int:
        return len(self._history)

    @property
    def history(self) -> tuple[str, ...]:
        return self._history

    @property
    def is_check(self) -> bool:
        return self._b.is_check()

    @property
    def is_game_over(self) -> bool:
        return self._b.is_game_over(claim_draw=True)

    @property
    def result(self) -> str | None:
        outcome = self._b.outcome(claim_draw=True)
        return outcome.result() if outcome else None

    @property
    def last_error(self) -> str | None:
        """上一次被拒的原因；成功落子后为 ``None``。"""
        return self._last_error

    # --- 棋盘 ---------------------------------------------------------
    @property
    def board(self) -> tuple[tuple[str, ...], ...]:
        """8×8 只读矩阵（``[0]`` 是第 8 横线），可直接 ``np.array(state.board)``。"""
        if self._matrix is None:
            self._matrix = tuple(
                tuple(
                    (p.symbol() if (p := self._b.piece_at(chess.square(f, r))) else ".")
                    for f in range(8)
                )
                for r in range(7, -1, -1)
            )
        return self._matrix

    @property
    def legal_moves(self) -> tuple[str, ...]:
        """当前全部合法着法（UCI，按字符串升序固定）。"""
        if self._legal is None:
            self._legal = tuple(sorted(m.uci() for m in self._b.legal_moves))
        return self._legal

    # --- 派生 ---------------------------------------------------------
    def apply(self, move: str) -> "State":
        """本地沙盘推演：返回走完这步的新快照，**不影响真实对局**。"""
        parsed = parse_uci(move)
        if parsed is None:
            raise IllegalMoveError("着法格式不对：%r（要写成 e2e4 这样的小写起终点）" % (move,))
        from_sq, to_sq, promo = parsed
        try:
            m = chess.Move.from_uci(from_sq + to_sq + promo)
        except ValueError as exc:  # 理论上 parse_uci 已挡住
            raise IllegalMoveError("着法无法解析：%r" % (move,)) from exc
        if m not in self._b.legal_moves:
            raise IllegalMoveError("非法着法：%s" % (move,))
        child = self._b.copy(stack=True)
        child.push(m)
        return State(child, self._history + (m.uci(),), None)

    def copy(self) -> "State":
        """快照本身不可变，直接返回自己。"""
        return self

    def pretty(self) -> str:
        """终端可读棋盘（含 FEN 与走子方）。"""
        side = "白方" if self._b.turn else "黑方"
        return "%s\nFEN: %s\n轮到: %s" % (self._b, self._b.fen(), side)

    def __repr__(self) -> str:
        return "State(ply=%d, turn=%r, fen=%r)" % (self.ply, self.turn, self.fen)
