"""``Client``：跨进程客户端，方法名与同进程 API 同构。

学生把 AI 放在别的进程/机器上时，用这个类代替 ``game`` 对象：
``c.submit("e2e4")`` 与 ``game.submit("e2e4")`` 返回同样的 ``Result``。
"""

import json
import time
from urllib import error, request

import chess

from .core.board import Board
from .core.result import Result
from .core.state import State


class Client:
    """HTTP 客户端（只依赖标准库）。"""

    def __init__(self, base_url, *, timeout=10.0, side=None):
        self.base_url = str(base_url).rstrip("/")
        self.timeout = float(timeout)
        self.side = side  # "w" / "b" / None：只用于 wait_my_turn

    # ------------------------------------------------------------------
    def _request(self, method, path, payload=None):
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = request.Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            try:
                return exc.code, json.loads(raw)
            except ValueError:
                return exc.code, {"result": {"code": -1, "reason": raw[:200]}}

    def _snapshot(self):
        status, body = self._request("GET", "/state")
        if status != 200:
            raise RuntimeError("GET /state 失败：HTTP %s" % (status,))
        return body

    # ------------------------------------------------------------------
    def state(self) -> State:
        body = self._snapshot()
        board = chess.Board(body["fen"])
        return State(board, body.get("history") or (), body.get("last_error"))

    def board(self) -> Board:
        return Board(chess.Board(self._snapshot()["fen"]))

    def legal_moves(self) -> tuple[str, ...]:
        """直接问服务端要合法着法（与 ``state.legal_moves`` 同序）。"""
        status, body = self._request("GET", "/legal_moves")
        if status != 200:
            raise RuntimeError("GET /legal_moves 失败：HTTP %s" % (status,))
        return tuple(body.get("legal_moves") or ())

    def submit(self, move) -> Result:
        status, body = self._request("POST", "/move", {"move": move})
        payload = body.get("result") or {}
        code = payload.get("code")
        if code is None:
            raise RuntimeError("POST /move 响应缺少 result.code（HTTP %s）" % (status,))
        return Result(int(code), payload.get("reason") or "", payload.get("move"))

    def reset(self, fen=None) -> Result:
        status, body = self._request("POST", "/reset", {"fen": fen} if fen else {})
        payload = body.get("result") or {"code": 0 if status == 200 else -2, "reason": ""}
        return Result(int(payload.get("code", 0)), payload.get("reason") or "", None)

    def wait_my_turn(self, timeout=10.0) -> bool:
        """阻塞到轮到自己；超时或对局结束返回 ``False``。"""
        deadline = time.monotonic() + float(timeout)
        while True:
            snapshot = self._snapshot()
            if snapshot.get("over"):
                return False
            if self.side is None or snapshot.get("turn") == self.side:
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.05)

    def pgn(self) -> str:
        req = request.Request(self.base_url + "/pgn", method="GET")
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read().decode("utf-8")
        except error.HTTPError as exc:
            raise RuntimeError("GET /pgn 失败：HTTP %s" % (exc.code,)) from exc

    def close(self):
        """无连接可关；保留该方法是让脚本能统一写 ``close()``。"""
