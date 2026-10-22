"""内置档位（L1 / L2 已在阶段 1 实现；L3–L5 见《使用说明书》§二）。

每档一个独立文件、50–150 行，学生可以直接读源码——这是刻意的教学设计。
"""

from .greedy import GreedyAgent
from .random_agent import RandomAgent

REGISTRY = {
    "random": RandomAgent,
    "greedy": GreedyAgent,
}


def available() -> list[str]:
    """已实现的内置档位（按难度排序）。"""
    return list(REGISTRY)


def make_builtin(name, *, seed=0):
    """按名字造一个内置 AI。"""
    if name not in REGISTRY:
        raise KeyError("没有这个内置档位：%r（现有：%s）" % (name, ", ".join(REGISTRY)))
    agent = REGISTRY[name]()
    agent.seed = seed
    return agent
