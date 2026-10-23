"""内置档位：L1 随机 / L2 贪心 / L3 minimax2 / L4 minimax3+αβ / L5 Stockfish。

每档一个独立文件、50–150 行，学生可以直接读源码——这是刻意的教学设计。
"""

import os

from .greedy import GreedyAgent
from .minimax2 import Minimax2Agent
from .minimax3 import Minimax3Agent
from .random_agent import RandomAgent
from .stockfish import StockfishAgent

REGISTRY = {
    "random": RandomAgent,
    "greedy": GreedyAgent,
    "minimax2": Minimax2Agent,
    "minimax3": Minimax3Agent,
    "stockfish": StockfishAgent,
}


def available() -> list[str]:
    """已注册的内置档位（按难度排序）。"""
    return list(REGISTRY)


def make_builtin(name, *, seed=0):
    """按名字造一个内置 AI。"""
    if name not in REGISTRY:
        raise KeyError("没有这个内置档位：%r（现有：%s）" % (name, ", ".join(REGISTRY)))
    if name == "stockfish":
        agent = StockfishAgent(
            elo=os.environ.get("CHESSARENA_STOCKFISH_ELO"),
            movetime=os.environ.get("CHESSARENA_STOCKFISH_MOVETIME"),
        )
    else:
        agent = REGISTRY[name]()
    agent.seed = seed
    return agent
