"""ChessArena 内核：裁判 / 棋盘 / 快照 / 选手 / 环境装配。"""

from .agent import Agent, HumanAgent, load_agent, resolve_player
from .arena import Arena
from .board import Board
from .errors import (
    AgentLoadError,
    ChessArenaError,
    ChessArenaTimeout,
    EngineError,
    GameOverError,
    IllegalMoveError,
    NotYourTurnError,
)
from .game import EVENTS, Game
from .moves import parse_uci, square, uci, xy
from .state import State

__all__ = [
    "Agent",
    "HumanAgent",
    "AgentLoadError",
    "Arena",
    "Board",
    "ChessArenaError",
    "ChessArenaTimeout",
    "EVENTS",
    "EngineError",
    "Game",
    "GameOverError",
    "IllegalMoveError",
    "NotYourTurnError",
    "State",
    "load_agent",
    "parse_uci",
    "resolve_player",
    "square",
    "uci",
    "xy",
]
