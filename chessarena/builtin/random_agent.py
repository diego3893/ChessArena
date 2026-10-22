"""L1 · 随机。从合法着法里随便挑一个。

这是最小可运行的 AI：它的存在证明"接口通了"，不证明"会下棋"。
"""

import random

from ..core.agent import Agent


class RandomAgent(Agent):
    name = "随机 (L1)"
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
        return self._random().choice(moves)
