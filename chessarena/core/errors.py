"""ChessArena 的异常族。

默认 ``strict=False``：落子失败只返回 ``Result``，不抛异常。
这些异常只在 ``strict=True`` 或显式 API（如 ``State.apply``）时出现，
所以初学者的代码基本不会遇到它们。
"""


class ChessArenaError(Exception):
    """所有 ChessArena 异常的基类。"""


class IllegalMoveError(ChessArenaError, ValueError):
    """着法不合法（``-1``），或 ``-2`` 格式错误。"""


class NotYourTurnError(ChessArenaError):
    """不是调用方该走的回合（``-3``）。"""


class GameOverError(ChessArenaError):
    """对局已经结束（``-4``）。"""


class ChessArenaTimeout(ChessArenaError):
    """等待或思考超时。对外导出名是 ``chessarena.TimeoutError``。"""


class AgentLoadError(ChessArenaError):
    """``agents/`` 下的模块导入失败、找不到 ``Agent`` 子类，或注册项非法。"""


class EngineError(ChessArenaError):
    """外部引擎（UCI 子进程）启动失败或异常退出。"""
