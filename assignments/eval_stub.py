"""第 2 周作业骨架：补全评估函数，然后当作"只数子"的 AI 用。

填完 TODO 后自测：
    python -m chessarena test assignments/eval_stub.py --vs builtin:greedy --games 10
"""

import chess

from chessarena import Agent, State

VALUE = {"P": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 0}


def evaluate(state):
    """返回白方视角的分数：正数白好、负数黑好。

    TODO 1：遍历 state.board（8×8，board[0] 是第 8 横线），大写=白、小写=黑。
    TODO 2：给中心格 / 兵推进加一点位置分（别超过子力的 1/10）。
    """
    score = 0
    for row in state.board:
        for cell in row:
            if cell == ".":
                continue
            # TODO 1：按 VALUE 累加；黑子要减
            pass
    return score


class MyEvalAgent(Agent):
    """一周只做"会数子"，不做搜索：挑评估最好的那一步。"""

    name = "我的评估"

    def choose_move(self, state):
        best_move = None
        best_score = None
        sign = 1 if state.turn == "w" else -1  # 统一成"我方视角"
        board = chess.Board(state.fen)  # 学生自己的规则库和沙盘
        for candidate in list(board.legal_moves):
            move = candidate.uci()
            board.push(candidate)
            child = State(board)
            score = sign * evaluate(child)
            board.pop()
            if best_score is None or score > best_score:
                best_move, best_score = move, score
        return best_move
