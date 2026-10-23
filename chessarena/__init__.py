"""ChessArena：单机国际象棋 AI 对战场。

学生只需要 ``from chessarena import Agent`` 并实现 ``choose_move(state)``。
"""

from .client import Client
from .core.agent import Agent, HumanAgent
from .core.arena import Arena
from .core.board import Board
from .core.errors import (
    AgentLoadError,
    ChessArenaError,
    ChessArenaTimeout,
    EngineError,
    GameOverError,
    IllegalMoveError,
    NotYourTurnError,
)
from .core.game import EVENTS, START_FEN, Game
from .core.moves import parse_uci, square, uci, xy
from .core.rc import RC
from .core.result import Result
from .core.state import State

#: 与《API总表》§9 的异常名对齐（内置 TimeoutError 的别名）
TimeoutError = ChessArenaTimeout

__version__ = "0.1.0-dev"

__all__ = [
    "Agent",
    "HumanAgent",
    "Arena",
    "Board",
    "Client",
    "EVENTS",
    "Game",
    "RC",
    "Result",
    "START_FEN",
    "State",
    "TimeoutError",
    "ChessArenaError",
    "ChessArenaTimeout",
    "IllegalMoveError",
    "NotYourTurnError",
    "GameOverError",
    "AgentLoadError",
    "EngineError",
    "load_agent",
    "parse_uci",
    "square",
    "uci",
    "xy",
    "__version__",
]


def load_agent(path, *, seed=0):
    """按路径加载学生 AI（``agents/my_agent.py``）。"""
    from .core.agent import load_agent as _load_agent

    return _load_agent(path, seed=seed)
