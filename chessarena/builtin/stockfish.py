"""L5 · Stockfish（经 UCI 子进程，可限制 ELO）。

它是"打不过"的那一档：默认限到 1600 分（``UCI_LimitStrength`` + ``UCI_Elo``），
调高到 2000+ 就是认真下也赢不了。学生可以用它来标定自己的棋力。
"""

import os

from ..core.agent import Agent
from ..engines.uci import UCIEngine


class StockfishAgent(Agent):
    name = "Stockfish (L5)"

    def __init__(self, path=None, *, elo=None, movetime=None, threads=1, hash_mb=64):
        super().__init__()
        self.elo = int(elo if elo is not None else os.environ.get("CHESSARENA_STOCKFISH_ELO", 1600))
        self.movetime = float(movetime if movetime is not None else 0.6)
        options = {
            "Threads": int(threads),
            "Hash": int(hash_mb),
        }
        if self.elo >= 1320:  # Stockfish 的 UCI_Elo 下限
            options["UCI_LimitStrength"] = True
            options["UCI_Elo"] = self.elo
        self._engine = UCIEngine(path, options=options, movetime=self.movetime)

    def choose_move(self, state):
        return self._engine.best_move(state.fen, movetime=self.movetime)

    def close(self):
        self._engine.close()
