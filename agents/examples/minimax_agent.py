"""完整样例：minimax + alpha-beta，只用平台的 ``State`` 接口。

平台仅提供State数据；本学生示例自行导入python-chess生成动作和推演。

运行：``python -m chessarena test agents/examples/minimax_agent.py --vs builtin:greedy --games 10``
"""

import time

import chess

from chessarena import Agent

VALUE = {"P": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 0}
MATE = 100000


class LocalPosition:
    """学生自己的搜索沙盘，不属于平台输入接口。"""

    def __init__(self, board):
        self.position = board
        self.board = tuple(tuple(board.piece_at(chess.square(f, r)).symbol()
                                 if board.piece_at(chess.square(f, r)) else "."
                                 for f in range(8)) for r in range(7, -1, -1))
        self.turn = "w" if board.turn else "b"
        self.is_game_over = board.is_game_over(claim_draw=True)
        outcome = board.outcome(claim_draw=True)
        self.result = outcome.result() if outcome else None
        self.legal_moves = tuple(sorted(move.uci() for move in board.legal_moves))

    def apply(self, move):
        child = self.position.copy()
        child.push_uci(move)
        return LocalPosition(child)


def piece_at(state, square):
    """``square`` 形如 "e4"；返回 'P'/'p'/'.'。"""
    file_index = ord(square[0]) - ord("a")
    rank = int(square[1])
    return state.board[8 - rank][file_index]


def evaluate(state):
    """白方视角的静态分：子力 + 兵推进。正数白好。"""
    score = 0
    for row_index, row in enumerate(state.board):
        rank = 8 - row_index  # 行 0 是第 8 横线
        for cell in row:
            if cell == ".":
                continue
            value = VALUE[cell.upper()]
            if cell == "P":
                value += 6 * (rank - 2)
            elif cell == "p":
                value += 6 * (7 - rank)
            score += value if cell.isupper() else -value
    return score


class MinimaxStudent(Agent):
    name = "样例·αβ 深度3"
    depth = 3

    def choose_move(self, state):
        state = LocalPosition(chess.Board(state.fen))
        started = time.monotonic()
        best, best_score = None, None
        alpha = -10 ** 9
        for move in self._ordered(state):
            score = -self._negamax(state.apply(move), self.depth - 1, -10 ** 9, -alpha)
            if best_score is None or score > best_score:
                best, best_score = move, score
            if score > alpha:
                alpha = score
            if time.monotonic() - started > 2.0:  # 兜底：别撞上 3s 的每步限时
                break
        return best

    def _negamax(self, state, depth, alpha, beta):
        if depth == 0 or state.is_game_over:
            return self._leaf(state)
        best = -10 ** 9
        for move in self._ordered(state):
            score = -self._negamax(state.apply(move), depth - 1, -beta, -alpha)
            if score > best:
                best = score
            if best > alpha:
                alpha = best
            if alpha >= beta:  # 剪枝
                break
        return best

    @staticmethod
    def _leaf(state):
        """叶子节点：换算成"当前走子方"视角（negamax 约定）。"""
        if state.is_game_over:
            if state.result in (None, "1/2-1/2"):
                return 0
            # 白胜 => 现在轮到的是黑方，黑方输了
            return -MATE if state.result == "1-0" else MATE
        score = evaluate(state)
        return score if state.turn == "w" else -score

    @staticmethod
    def _ordered(state):
        """吃子优先（被吃子越大越靠前），没有吃子就按着法串排序。"""
        def key(move):
            victim = piece_at(state, move[2:4])
            return (VALUE.get(victim.upper(), 0) if victim != "." else 0)

        return sorted(state.legal_moves, key=key, reverse=True)
