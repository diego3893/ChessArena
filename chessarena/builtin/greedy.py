"""L2 · 贪心。只看一步：优先吃掉价值最高的子，否则随机走。

它不会搜索、不会防守，所以经常自己送子——这正是课堂上要展示的"没有前瞻"。
"""

import random

import chess

from ..core.agent import Agent

VALUE = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}


class GreedyAgent(Agent):
    name = "贪心 (L2)"
    fast_local = True

    def __init__(self):
        super().__init__()
        self._rng = random.Random(0)
        self._rng_seed = 0

    def _random(self):
        if self._rng_seed != self.seed:
            self._rng = random.Random(self.seed)
            self._rng_seed = self.seed
        return self._rng

    def choose_move(self, state):
        moves = state.legal_moves
        if not moves:
            return None

        board = chess.Board(state.fen)
        best_score = -1
        best_moves = []
        for move_uci in moves:
            move = chess.Move.from_uci(move_uci)
            score = 0
            captured = board.piece_at(move.to_square)
            if captured is not None:
                score = VALUE[captured.piece_type]
            # 升变也算收益
            if move.promotion:
                score += VALUE[move.promotion]
            if score > best_score:
                best_score = score
                best_moves = [move_uci]
            elif score == best_score:
                best_moves.append(move_uci)

        if best_score <= 0:
            return self._random().choice(moves)
        return self._random().choice(best_moves)
