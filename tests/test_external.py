"""外部对手与 agents 目录：agents.json 注册、HTTP 对手、扫描。"""

import json
import shutil
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import chess

from chessarena import Arena
from chessarena.core.agent import scan_agents
from chessarena.core.errors import AgentLoadError, TransientError
from chessarena.core.external import HttpAgent, load_registry, resolve_external
from chessarena.core.state import State


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802（标准库命名）
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        if getattr(self.server, "fail", False):
            body = b"boom"
            self.send_response(500)
        else:
            body = json.dumps({"move": self.server.move}).encode("utf-8")
            self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class TestRegistry(unittest.TestCase):
    def setUp(self):
        self.base = Path("runs") / "test-agents"
        shutil.rmtree(self.base, ignore_errors=True)
        self.base.mkdir(parents=True)
        self.registry = self.base / "agents.json"

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def _write(self, entries):
        self.registry.write_text(json.dumps(entries), encoding="utf-8")

    def test_missing_file_is_empty(self):
        self.assertEqual(load_registry(self.base / "nope.json"), [])

    def test_load_and_validate(self):
        self._write([{"name": "bot", "type": "uci", "cmd": ["x"]},
                     {"name": "svc", "type": "http", "url": "http://127.0.0.1:9/"}])
        entries = load_registry(self.registry)
        self.assertEqual([e["name"] for e in entries], ["bot", "svc"])

    def test_invalid_entries(self):
        self._write([{"name": "x", "type": "uci"}])           # 缺 cmd
        with self.assertRaises(AgentLoadError):
            load_registry(self.registry)
        self._write([{"name": "x", "type": "nope"}])
        with self.assertRaises(AgentLoadError):
            load_registry(self.registry)
        self._write([{"name": "x", "type": "uci", "cmd": ["a"]},
                     {"name": "x", "type": "uci", "cmd": ["b"]}])
        with self.assertRaises(AgentLoadError):
            load_registry(self.registry)

    def test_resolve_unknown(self):
        self._write([{"name": "bot", "type": "uci", "cmd": ["x"]}])
        with self.assertRaises(AgentLoadError):
            resolve_external("uci:nope", path=self.registry)
        with self.assertRaises(AgentLoadError):
            resolve_external("http:bot", path=self.registry)  # 类型不匹配


class TestHttpAgent(unittest.TestCase):
    def _server(self, move="e2e4", fail=False):
        server = HTTPServer(("127.0.0.1", 0), _Handler)
        server.move = move
        server.fail = fail
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return "http://127.0.0.1:%d/move" % (server.server_address[1],)

    def test_returns_engine_move(self):
        agent = HttpAgent("云端", self._server(move="g1f3"))
        state = State(chess.Board())
        self.assertEqual(agent.choose_move(state), "g1f3")

    def test_http_error_is_transient(self):
        agent = HttpAgent("云端", self._server(fail=True))
        with self.assertRaises(TransientError):
            agent.choose_move(State(chess.Board()))


class TestScan(unittest.TestCase):
    def setUp(self):
        self.base = Path("runs") / "test-scan"
        shutil.rmtree(self.base, ignore_errors=True)
        self.base.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_scans_python_and_registry(self):
        (self.base / "my_agent.py").write_text(
            "from chessarena import Agent\n"
            "class MyAgent(Agent):\n"
            "    name = '张三'\n"
            "    def choose_move(self, state):\n"
            "        return state.legal_moves[0]\n",
            encoding="utf-8",
        )
        (self.base / "broken.py").write_text("raise RuntimeError('oops')\n", encoding="utf-8")
        (self.base / "agents.json").write_text(json.dumps([
            {"name": "外部引擎", "type": "uci", "cmd": ["noop.exe"]},
        ]), encoding="utf-8")

        pairs = scan_agents(self.base, seed=0)
        infos = [info for info, error in pairs if error is None]
        errors = [info for info, error in pairs if error is not None]
        self.assertEqual(len(errors), 1)  # broken.py 被跳过
        specs = {info.spec for info in infos}
        self.assertTrue(any(s.endswith("my_agent.py") for s in specs), specs)
        self.assertIn("uci:外部引擎", specs)
        names = {info.name for info in infos}
        self.assertIn("张三", names)
        self.assertIn("外部引擎", names)

    def test_arena_agents_uses_directory(self):
        (self.base / "helper.py").write_text(
            "from chessarena import Agent\n"
            "class Helper(Agent):\n"
            "    name = 'helper'\n"
            "    def choose_move(self, state):\n"
            "        return state.legal_moves[0]\n",
            encoding="utf-8",
        )
        arena = Arena(live=False, agents_dir=self.base, config="__no_such_config__.yaml")
        try:
            infos = arena.agents()
            self.assertEqual([info.name for info in infos], ["helper"])
            game = arena.new_game(white=infos[0].spec, black="builtin:random")
            self.assertTrue(game.submit(game.state.legal_moves[0]).ok)
        finally:
            arena.close()


if __name__ == "__main__":
    unittest.main()
