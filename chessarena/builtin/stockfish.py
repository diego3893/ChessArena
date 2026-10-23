"""L5 · Stockfish（经 UCI 子进程，可限制 ELO）。

它是"打不过"的那一档：默认限到 **2600** 分（``UCI_LimitStrength`` + ``UCI_Elo``），
每步 1.0 秒。想温柔一点就调低（最低 1320），想更狠就调高（最高 3190）：

| 位置 | 写法 |
|---|---|
| `config.yaml` | `stockfish: {elo: 2600, movetime: 1.0}` |
| 环境变量 | `CHESSARENA_STOCKFISH_ELO=1600`、`CHESSARENA_STOCKFISH_MOVETIME=0.5` |
| 代码 | `StockfishAgent(elo=1800, movetime=0.8)` |

环境变量优先于 `config.yaml`，方便课堂临时调档。
"""

import os

from ..core.agent import Agent
from ..engines.uci import UCIEngine

DEFAULT_ELO = 2600
DEFAULT_MOVETIME = 1.0


class StockfishAgent(Agent):
    name = "Stockfish (L5)"

    def __init__(self, path=None, *, elo=None, movetime=None, threads=1, hash_mb=64):
        super().__init__()
        elo = elo if elo is not None else os.environ.get("CHESSARENA_STOCKFISH_ELO", DEFAULT_ELO)
        movetime = (movetime if movetime is not None
                    else os.environ.get("CHESSARENA_STOCKFISH_MOVETIME", DEFAULT_MOVETIME))
        self.elo = int(elo)
        self.movetime = float(movetime)
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
