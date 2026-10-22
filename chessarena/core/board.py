"""``Board``：棋盘的只读视图。

**没有任何写方法**，这是刻意的——唯一写入口是 ``Game.submit()``。
每次读取都从裁判当前的 ``chess.Board`` 现算，所以它永远是同一份真相。
"""

import chess

from ..core.moves import xy


def _symbols_row(board: chess.Board, rank: int) -> list[str]:
    row = []
    for file in range(8):
        piece = board.piece_at(chess.square(file, rank))
        row.append(piece.symbol() if piece else ".")
    return row


class Board:
    """只读棋盘视图。"""

    __slots__ = ("_b",)

    def __init__(self, board: chess.Board):
        self._b = board

    # --- 基本读取 -----------------------------------------------------
    @property
    def fen(self) -> str:
        return self._b.fen()

    @property
    def turn(self) -> str:
        return "w" if self._b.turn else "b"

    @property
    def is_check(self) -> bool:
        return self._b.is_check()

    @property
    def is_game_over(self) -> bool:
        return self._b.is_game_over(claim_draw=True)

    @property
    def result(self) -> str | None:
        """从白方视角的结果：``"1-0"`` / ``"0-1"`` / ``"1/2-1/2"`` / ``None``。"""
        outcome = self._b.outcome(claim_draw=True)
        return outcome.result() if outcome else None

    @property
    def legal_moves(self) -> tuple[str, ...]:
        """当前全部合法着法（UCI，顺序固定：按字符串升序）。"""
        return tuple(sorted(m.uci() for m in self._b.legal_moves))

    # --- 单格读取 -----------------------------------------------------
    def get(self, x: int, y: int) -> str:
        """``board.get(4, 3)`` 取 e4：返回 ``'P'``/``'p'``/``'.'``。"""
        sq = chess.square(x, y)
        piece = self._b.piece_at(sq)
        return piece.symbol() if piece else "."

    def piece_at(self, sq: str) -> str:
        """``board.piece_at("e4")``：同上，用格名索引。"""
        x, y = xy(sq)
        return self.get(x, y)

    def is_empty(self, x: int, y: int) -> bool:
        return self.get(x, y) == "."

    def moves_from(self, sq: str) -> list[str]:
        """某个格子的棋子能走到哪些格（UI 高亮/教学用），按格名排序。"""
        try:
            from_sq = chess.parse_square(sq)
        except (ValueError, TypeError):
            return []
        targets = {
            m.uci()[2:4]
            for m in self._b.legal_moves
            if m.from_square == from_sq
        }
        return sorted(targets)

    # --- 整盘读取 -----------------------------------------------------
    def matrix(self) -> list[list[str]]:
        """8×8 二维列表：``[0]`` 是第 8 横线（黑方底线），可直接 ``np.array()``。"""
        return [_symbols_row(self._b, rank) for rank in range(7, -1, -1)]

    def ascii(self) -> str:
        """终端字符画（``K``/``q``/``.``）。"""
        return str(self._b)

    def __repr__(self) -> str:
        return "Board(fen=%r)" % (self.fen,)
