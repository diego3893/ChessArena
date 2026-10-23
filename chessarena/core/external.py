"""外部对手：``agents/agents.json`` 里的 UCI 引擎与 HTTP 服务。

协议见《API总表》§15：UCI 走标准握手，HTTP 走一次 POST。两者都只是"被裁判驱动的一方"，
落子仍然只经 ``Game.submit()``。
"""

import json
from pathlib import Path
from urllib import error, request

import chess
import chess.engine

from .agent import Agent
from .errors import AgentLoadError, EngineError, TransientError

REGISTRY_PATH = "agents/agents.json"


def load_registry(path=REGISTRY_PATH):
    """读并校验 ``agents.json``；文件不存在返回空表。"""
    p = Path(path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise AgentLoadError("agents.json 不是合法 JSON：%s" % (exc,)) from exc
    if not isinstance(data, list):
        raise AgentLoadError("agents.json 顶层必须是数组")
    entries = []
    seen = set()
    for item in data:
        if not isinstance(item, dict) or not item.get("name"):
            raise AgentLoadError("agents.json 条目缺少 name：%r" % (item,))
        kind = item.get("type")
        if kind not in ("uci", "http"):
            raise AgentLoadError("%s 的 type 只能是 uci / http" % (item["name"],))
        if item["name"] in seen:
            raise AgentLoadError("agents.json 名字重复：%s" % (item["name"],))
        seen.add(item["name"])
        if kind == "uci" and not item.get("cmd"):
            raise AgentLoadError("%s 缺少 cmd" % (item["name"],))
        if kind == "http" and not item.get("url"):
            raise AgentLoadError("%s 缺少 url" % (item["name"],))
        entries.append(item)
    return entries


def resolve_external(spec, *, path=REGISTRY_PATH, seed=0):
    """``"uci:名字"`` / ``"http:名字"`` → 对应的 Agent 实例。"""
    kind, _, name = str(spec).partition(":")
    entries = load_registry(path)
    for item in entries:
        if item["name"] != name:
            continue
        if item["type"] != kind:
            raise AgentLoadError("%s 的类型是 %s，不是 %s" % (name, item["type"], kind))
        if kind == "uci":
            return UciAgent(item["name"], item["cmd"], options=item.get("options"),
                            timeout=item.get("timeout", 5.0))
        return HttpAgent(item["name"], item["url"], timeout=item.get("timeout", 10.0))
    raise AgentLoadError("agents.json 里没有 %r（现有：%s）"
                         % (name, "、".join(e["name"] for e in entries) or "空"))


class UciAgent(Agent):
    """把一个 UCI 引擎包成 ``Agent``（懒启动、可复用）。"""

    def __init__(self, name, cmd, *, options=None, timeout=5.0):
        super().__init__()
        self.name = name
        self.cmd = list(cmd) if isinstance(cmd, (list, tuple)) else [str(cmd)]
        self.options = dict(options or {})
        self.timeout = float(timeout)
        self._engine = None

    def _ensure(self):
        if self._engine is not None:
            return self._engine
        try:
            engine = chess.engine.SimpleEngine.popen_uci(self.cmd, timeout=10.0)
        except Exception as exc:
            raise EngineError("启动引擎失败：%s（%r）" % (" ".join(self.cmd), exc)) from exc
        for key, value in self.options.items():
            try:
                engine.configure({key: value})
            except Exception as exc:
                raise EngineError("引擎选项 %s=%r 不被接受：%r" % (key, value, exc)) from exc
        self._engine = engine
        return engine

    def choose_move(self, state):
        engine = self._ensure()
        board = chess.Board(state.fen)
        limit = chess.engine.Limit(time=max(0.05, self.timeout * 0.9))
        try:
            result = engine.play(board, limit)
        except chess.engine.EngineTerminatedError as exc:
            raise TransientError("引擎退出：%r" % (exc,)) from exc
        return result.move.uci() if result.move else None

    def close(self):
        engine, self._engine = self._engine, None
        if engine is not None:
            try:
                engine.quit()
            except Exception:
                pass


class HttpAgent(Agent):
    """POST ``{"fen","turn","ply","history","legal_moves"}``，读回 ``{"move": ...}``。"""

    def __init__(self, name, url, *, timeout=10.0):
        super().__init__()
        self.name = name
        self.url = url
        self.timeout = float(timeout)

    def choose_move(self, state):
        payload = {
            "fen": state.fen,
            "turn": state.turn,
            "ply": state.ply,
            "history": list(state.history),
            "legal_moves": list(state.legal_moves),
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(self.url, data=data,
                              headers={"Content-Type": "application/json"}, method="POST")
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:200]
            raise TransientError("HTTP %s：%s" % (exc.code, detail)) from exc
        except (error.URLError, TimeoutError, ValueError) as exc:
            raise TransientError("HTTP 请求失败：%r" % (exc,)) from exc
        move = (body or {}).get("move")
        return move if isinstance(move, str) else None
