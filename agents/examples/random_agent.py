"""最小可运行的学生 AI（10 行）。

平台在每一步调用 `choose_move`，把返回值交给裁判校验并落在真实棋盘上。
"""

from chessarena import Agent


class RandomStudent(Agent):
    name = "样例·随机"

    def choose_move(self, state):
        # state.legal_moves 是当前所有合法着法（UCI 字符串，顺序固定）
        return state.legal_moves[0]
