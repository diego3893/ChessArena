"""只读棋子视图，不持有规则引擎，不提供合法着法。"""

from .moves import xy
from .state import State


class Board:
    __slots__ = ("__read",)

    def __init__(self, board):
        state = board if isinstance(board, State) else State(board)
        self.__read = lambda: state

    @classmethod
    def _live(cls, read):
        view = cls.__new__(cls)
        view.__read = read
        return view

    @property
    def fen(self):
        return self.__read().fen

    @property
    def turn(self):
        return self.__read().turn

    @property
    def is_check(self):
        return self.__read().is_check

    @property
    def is_game_over(self):
        return self.__read().is_game_over

    @property
    def result(self):
        return self.__read().result

    def get(self, x, y):
        if not (0 <= x < 8 and 0 <= y < 8):
            raise ValueError("棋盘坐标须在0..7之间")
        return self.__read().board[7-y][x]

    def piece_at(self, sq):
        return self.get(*xy(sq))

    def is_empty(self, x, y):
        return self.get(x, y) == "."

    def matrix(self):
        return [list(row) for row in self.__read().board]

    def ascii(self):
        return "\n".join(" ".join(row) for row in self.__read().board)

    def __repr__(self):
        return "Board(fen=%r)" % self.fen
