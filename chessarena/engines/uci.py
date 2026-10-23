"""UCI 引擎适配（用 python-chess 的 ``SimpleEngine`` 走标准 UCI 握手）。

与《API总表》§15.2 描述的是同一套协议：``uci`` / ``isready`` / ``position fen`` /
``go movetime`` / ``bestmove``。python-chess 负责收发，我们只管生命周期与选项。
"""

import os
from pathlib import Path

import chess
import chess.engine

from ..core.errors import EngineError

#: 默认放在 thirdparty/ 下的官方 Stockfish
DEFAULT_STOCKFISH = "thirdparty/stockfish-windows-x86-64-universal.exe"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_stockfish_path(path=None) -> Path:
    """按 参数 → 环境变量 → 默认路径 的顺序找引擎可执行文件。"""
    candidates = [path, os.environ.get("CHESSARENA_STOCKFISH"), DEFAULT_STOCKFISH]
    for candidate in candidates:
        if not candidate:
            continue
        p = Path(candidate)
        if not p.is_absolute():
            p = project_root() / p
        if p.is_file():
            return p
    raise EngineError(
        "找不到 Stockfish 可执行文件。把官方 exe 放到 thirdparty/，"
        "或设置环境变量 CHESSARENA_STOCKFISH 指向 exe。"
    )


class UCIEngine:
    """一个 UCI 引擎进程（懒启动、可复用、显式关闭）。"""

    def __init__(self, path=None, *, options=None, movetime=0.6, startup_timeout=10.0):
        self.path = resolve_stockfish_path(path)
        self.options = dict(options or {})
        self.movetime = float(movetime)
        self.startup_timeout = float(startup_timeout)
        self._engine = None

    # ------------------------------------------------------------------
    def start(self):
        if self._engine is not None:
            return self
        try:
            self._engine = chess.engine.SimpleEngine.popen_uci(
                str(self.path), timeout=self.startup_timeout
            )
        except Exception as exc:  # 路径/权限/协议问题统一成 EngineError
            raise EngineError("启动引擎失败：%s（%r）" % (self.path, exc)) from exc
        for name, value in self.options.items():
            try:
                self._engine.configure({name: value})
            except Exception as exc:
                self.close()
                raise EngineError("引擎选项 %s=%r 不被接受：%r" % (name, value, exc)) from exc
        return self

    def best_move(self, fen, *, movetime=None) -> str | None:
        """给一个 FEN，返回引擎认为最好的一步（UCI）；无着法时返回 None。"""
        self.start()
        board = chess.Board(fen)
        limit = chess.engine.Limit(time=float(movetime or self.movetime))
        try:
            result = self._engine.play(board, limit)
        except chess.engine.EngineTerminatedError as exc:
            raise EngineError("引擎异常退出：%r" % (exc,)) from exc
        except chess.engine.EngineError as exc:
            raise EngineError("引擎报错：%r" % (exc,)) from exc
        return result.move.uci() if result.move else None

    def close(self):
        engine, self._engine = self._engine, None
        if engine is None:
            return
        try:
            engine.quit()
        except Exception:
            try:
                engine.close()
            except Exception:
                pass

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.close()
        return False
