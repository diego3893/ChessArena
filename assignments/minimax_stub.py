"""第 3 周作业骨架：补全 minimax（先不要 alpha-beta）。

填完 TODO 后自测：
    python -m chessarena test assignments/minimax_stub.py --vs builtin:greedy --games 10

对照答案：agents/examples/minimax_agent.py（深度 3 + alpha-beta）。
"""

from chessarena import Agent

MATE = 100000
VALUE = {"P": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 0}


def evaluate(state):
    """白方视角的静态分（子力就够用了）。"""
    score = 0
    for row in state.board:
        for cell in row:
            if cell == ".":
                continue
            value = VALUE[cell.upper()]
            score += value if cell.isupper() else -value
    return score


class MyMinimax(Agent):
    name = "我的 minimax"
    depth = 2

    def choose_move(self, state):
        best_move, best_score = None, None
        for move in state.legal_moves:
            score = self.minimax(state.apply(move), self.depth - 1)
            if best_score is None or score > best_score:
                best_move, best_score = move, score
        return best_move

    def minimax(self, state, depth):
        """返回"当前走子方"视角的分数。

        TODO 1：depth == 0 或 state.is_game_over 时返回叶子分数
                （白方视角的 evaluate 要按 state.turn 翻成当前走子方视角；
                 将杀返回 ±MATE，和棋返回 0）。
        TODO 2：遍历 state.legal_moves，对每个 state.apply(move) 递归，
                当前方取最大值。
        """
        if depth == 0 or state.is_game_over:
            # TODO 1
            raise NotImplementedError("补全叶子分数")

        best = -10 ** 9
        for move in state.legal_moves:
            # TODO 2
            raise NotImplementedError("补全递归")
        return best
