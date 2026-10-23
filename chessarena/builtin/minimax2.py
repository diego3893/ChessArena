"""L3 · minimax 深度 2（无剪枝）。

只看"我走一步、对手回一步"之后的子力对比。它的意义是把 minimax 的骨架
摊开给人看：递归 + 双方轮流取 max/min，没有别的魔法。
"""

import chess

from ..core.agent import Agent
from .evaluation import evaluate


class Minimax2Agent(Agent):
    name = "Minimax 深度2 (L3)"

    def choose_move(self, state):
        board = chess.Board(state.fen)
        best_score = None
        best_move = None
        for move in board.legal_moves:
            board.push(move)
            score = self._minimax(board, depth=1, white_to_move=False)
            board.pop()
            if best_score is None or score > best_score:
                best_score, best_move = score, move
        return best_move.uci() if best_move else None

    def _minimax(self, board, depth, white_to_move):
        """返回白方视角的分数。``depth`` 是还要往下几层。"""
        if depth == 0 or board.is_game_over(claim_draw=False):
            return evaluate(board)

        scores = []
        for move in board.legal_moves:
            board.push(move)
            scores.append(self._minimax(board, depth - 1, not white_to_move))
            board.pop()
        if not scores:
            return evaluate(board)
        return max(scores) if white_to_move else min(scores)
