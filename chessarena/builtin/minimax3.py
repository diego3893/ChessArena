"""L4 · minimax 深度 3 + alpha-beta（比 L3 多的就是剪枝与着法排序）。

教学点在这里：同样的评估函数、同样的递归骨架，只加了十几行 alpha-beta，
就能多搜一层。上限用"迭代加深 + 时间预算"兜住，保证每步不会超出课堂时限。
"""

import time

import chess

from ..core.agent import Agent
from .evaluation import evaluate, value_of


class _Timeout(Exception):
    pass


class Minimax3Agent(Agent):
    name = "Minimax 深度3 αβ (L4)"

    def __init__(self, budget=0.85, max_depth=4):
        super().__init__()
        self.budget = float(budget)
        self.max_depth = int(max_depth)

    def choose_move(self, state):
        board = chess.Board(state.fen)
        deadline = time.monotonic() + self.budget
        best_move = None
        for depth in range(1, self.max_depth + 1):
            try:
                candidate = self._search_root(board, depth, deadline)
            except _Timeout:
                break
            if candidate is not None:
                best_move = candidate
            if time.monotonic() >= deadline:
                break
        return best_move.uci() if best_move else None

    # ------------------------------------------------------------------
    def _search_root(self, board, depth, deadline):
        best_move = None
        best_score = None
        alpha = -10 ** 9
        for move in self._ordered(board):
            board.push(move)
            try:
                score = -self._negamax(board, depth - 1, -10 ** 9, -alpha, deadline)
            finally:
                board.pop()
            if best_score is None or score > best_score:
                best_score, best_move = score, move
            if score > alpha:
                alpha = score
        return best_move

    def _negamax(self, board, depth, alpha, beta, deadline):
        if time.monotonic() > deadline:
            raise _Timeout
        if depth == 0 or board.is_game_over(claim_draw=False):
            score = evaluate(board)
            return score if board.turn else -score

        best = -10 ** 9
        for move in self._ordered(board):
            board.push(move)
            try:
                score = -self._negamax(board, depth - 1, -beta, -alpha, deadline)
            finally:
                board.pop()
            if score > best:
                best = score
            if best > alpha:
                alpha = best
            if alpha >= beta:  # 剪枝：对手不会走到这里
                break
        return best

    @staticmethod
    def _ordered(board):
        """吃子优先，按 MVV-LVA 排（被吃子越大、动用的子越小越靠前）。"""
        def score(move):
            victim = board.piece_at(move.to_square)
            attacker = board.piece_at(move.from_square)
            return value_of(victim) * 10 - value_of(attacker)

        return sorted(board.legal_moves, key=score, reverse=True)
