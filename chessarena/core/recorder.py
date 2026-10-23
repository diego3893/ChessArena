"""录像：把一局的每个事件写成 JSONL。

一行一个事件，字段与《API总表》§16.3 对齐，另加 ``t``（相对开局秒数）。
回放器只读这个文件，不需要重新跑棋。
"""

import json
import time
from pathlib import Path


class Recorder:
    """把 ``Game`` 的事件流落到 ``runs/<game_id>.jsonl``。"""

    def __init__(self, path, *, game=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._started = time.monotonic()
        self._handle = self.path.open("w", encoding="utf-8")
        self._closed = False
        if game is not None:
            self.attach(game)

    def attach(self, game):
        game.on("move", lambda move, result: self._write(
            "move", move=move, ply=game.ply, state=game.to_json()))
        game.on("illegal", lambda move, result: self._write(
            "illegal", move=move, code=result.code, reason=result.reason))
        game.on("game_over", lambda result, reason: self._write(
            "game_over", result=result, reason=reason, state=game.to_json()))
        game.on("retry", lambda side, attempt, result: self._write(
            "retry", side=side, attempt=attempt, code=result.code, reason=result.reason))
        game.on("timeout", lambda side, seconds: self._write(
            "timeout", side=side, seconds=round(float(seconds), 3)))
        return self

    def _write(self, kind, **fields):
        if self._closed:
            return
        payload = {"type": kind, "t": round(time.monotonic() - self._started, 3)}
        payload.update(fields)
        self._handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._handle.flush()

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self._handle.close()
        except OSError:
            pass
