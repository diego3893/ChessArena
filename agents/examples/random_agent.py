"""最小可运行的学生 AI（10 行）。

平台在每一步调用 `choose_move`，把返回值交给裁判校验并落在真实棋盘上。
"""

import chess

from chessarena import Agent


class RandomStudent(Agent):
    name = "样例·随机"

    def choose_move(self, state):
        # 学生自行导入规则库；平台仅提供局面数据。
        board = chess.Board(state.fen)
        return sorted(move.uci() for move in board.legal_moves)[0]
