"""阶段 2 集成测试：HTTP 端点、WebSocket 推送、Client 同构、录像。

每个测试自己起一个 uvicorn（随机端口，后台线程），跑完关掉。
"""

import json
import shutil
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import uvicorn
from websockets.sync.client import connect

from chessarena import Arena, Client, RC
from chessarena.web.server import create_app
from chessarena.web.session import Session


class ServerFixture:
    """在后台线程里跑一个真实 uvicorn。"""

    def __init__(self, white, black, *, speed=4.0, heartbeat=0.2):
        self.arena = Arena(live=True, seed=0, config="__no_such_config__.yaml")
        self.session = Session(self.arena, white, black, speed=speed, heartbeat=heartbeat)
        self.app = create_app(self.session)
        self.server = uvicorn.Server(uvicorn.Config(
            self.app, host="127.0.0.1", port=0, log_level="error", lifespan="on"
        ))
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def __enter__(self):
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started:
            if time.monotonic() > deadline:
                raise RuntimeError("uvicorn 启动超时")
            time.sleep(0.02)
        self.port = self.server.servers[0].sockets[0].getsockname()[1]
        self.base = "http://127.0.0.1:%d" % (self.port,)
        self.ws = "ws://127.0.0.1:%d/ws" % (self.port,)
        return self

    def __exit__(self, *exc):
        self.server.should_exit = True
        self.thread.join(timeout=5)
        self.session.stop()
        self.arena.close()
        return False

    # --- 便捷 HTTP ---------------------------------------------------
    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def post(self, path, payload):
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def wait_ply(self, at_least, timeout=8.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            _, state = self.get("/state")
            if state["ply"] >= at_least:
                return state
            time.sleep(0.03)
        raise AssertionError("等待 ply>=%d 超时" % (at_least,))


class TestHttpEndpoints(unittest.TestCase):
    def test_state_and_legal_moves(self):
        with ServerFixture("human", "builtin:greedy") as fx:
            status, state = fx.get("/state")
            self.assertEqual(status, 200)
            self.assertEqual(state["turn"], "w")
            self.assertEqual(state["ply"], 0)
            self.assertEqual(len(state["legal_moves"]), 20)
            self.assertEqual(state["history"], [])

            status, legal = fx.get("/legal_moves")
            self.assertEqual(status, 200)
            self.assertEqual(tuple(legal["legal_moves"]), tuple(state["legal_moves"]))

    def test_move_ok_then_ai_replies(self):
        with ServerFixture("human", "builtin:greedy") as fx:
            status, body = fx.post("/move", {"move": "e2e4"})
            self.assertEqual(status, 200)
            self.assertEqual(body["result"]["code"], 0)
            self.assertEqual(body["state"]["ply"], 1)
            self.assertEqual(body["state"]["turn"], "b")
            after = fx.wait_ply(2)
            self.assertEqual(after["turn"], "w")

    def test_move_illegal_is_400(self):
        with ServerFixture("human", "builtin:greedy") as fx:
            status, body = fx.post("/move", {"move": "e2e5"})
            self.assertEqual(status, 400)
            self.assertEqual(body["result"]["code"], RC.ILLEGAL_MOVE)
            self.assertEqual(body["state"]["ply"], 0)

    def test_move_bad_format_is_400(self):
        with ServerFixture("human", "builtin:greedy") as fx:
            status, body = fx.post("/move", {"move": "Nf3"})
            self.assertEqual(status, 400)
            self.assertEqual(body["result"]["code"], RC.BAD_FORMAT)

    def test_move_when_ai_turn_is_409(self):
        with ServerFixture("builtin:random", "builtin:random") as fx:
            fx.post("/control", {"action": "pause"})  # 冻结局面，避免 AI 回合快速翻页
            status, body = fx.post("/move", {"move": "e2e4"})
            self.assertEqual(status, 409)
            self.assertEqual(body["result"]["code"], RC.NOT_YOUR_TURN)

    def test_reset(self):
        with ServerFixture("human", "builtin:greedy") as fx:
            fx.post("/move", {"move": "e2e4"})
            status, body = fx.post("/reset", {})
            self.assertEqual(status, 200)
            self.assertEqual(body["state"]["ply"], 0)
            self.assertEqual(body["state"]["turn"], "w")

    def test_pgn(self):
        with ServerFixture("human", "builtin:greedy") as fx:
            fx.post("/move", {"move": "e2e4"})
            fx.wait_ply(2)
            with urllib.request.urlopen(fx.base + "/pgn", timeout=5) as resp:
                text = resp.read().decode("utf-8")
            self.assertIn("[Event \"ChessArena\"]", text)
            self.assertIn("e4", text)

    def test_control_pause_step_resume(self):
        with ServerFixture("builtin:random", "builtin:random", speed=20.0) as fx:
            status, body = fx.post("/control", {"action": "pause"})
            self.assertEqual(status, 200)
            self.assertTrue(body["paused"])
            time.sleep(0.2)
            ply_paused = fx.get("/state")[1]["ply"]
            time.sleep(0.3)
            self.assertEqual(fx.get("/state")[1]["ply"], ply_paused, "暂停后仍在走子")

            fx.post("/control", {"action": "step"})
            self.assertEqual(fx.get("/state")[1]["ply"], ply_paused + 1)

            fx.post("/control", {"action": "resume"})
            time.sleep(0.3)
            self.assertGreaterEqual(fx.get("/state")[1]["ply"], ply_paused + 1)

    def test_control_speed_and_unknown(self):
        with ServerFixture("builtin:random", "builtin:random") as fx:
            status, body = fx.post("/control", {"action": "speed", "speed": 2})
            self.assertEqual(status, 200)
            self.assertAlmostEqual(body["speed"], 2.0)
            status, body = fx.post("/control", {"action": "nope"})
            self.assertEqual(status, 400)


class TestClient(unittest.TestCase):
    def test_client_isomorphic(self):
        with ServerFixture("human", "builtin:greedy") as fx:
            client = Client(fx.base, side="w")
            state = client.state()
            self.assertEqual(state.turn, "w")
            self.assertEqual(len(state.legal_moves), 20)
            self.assertEqual(state.fen, fx.get("/state")[1]["fen"])
            self.assertEqual(client.legal_moves(), state.legal_moves)

            self.assertEqual(client.submit("Nf3"), RC.BAD_FORMAT)
            self.assertEqual(client.submit("e2e5"), RC.ILLEGAL_MOVE)
            result = client.submit("e2e4")
            self.assertTrue(result.ok)
            self.assertEqual(result.move, "e2e4")
            fx.wait_ply(2)

            self.assertTrue(client.wait_my_turn(timeout=5))
            self.assertEqual(client.board().piece_at("e4"), "P")

            self.assertTrue(client.reset().ok)
            self.assertEqual(client.state().ply, 0)

    def test_client_game_over_code(self):
        with ServerFixture("human", "human") as fx:
            for move in ("f2f3", "e7e5", "g2g4", "d8h4"):
                status, body = fx.post("/move", {"move": move})
                self.assertEqual(status, 200, msg=body)
            status, body = fx.post("/move", {"move": "a2a3"})
            self.assertEqual(status, 410)
            self.assertEqual(body["result"]["code"], RC.GAME_OVER)


class TestWebSocket(unittest.TestCase):
    def test_hello_move_game_over(self):
        with ServerFixture("human", "human") as fx:
            with connect(fx.ws) as ws:
                hello = json.loads(ws.recv(timeout=5))
                self.assertEqual(hello["type"], "hello")
                self.assertEqual(hello["state"]["turn"], "w")

                fx.post("/move", {"move": "f2f3"})
                first = json.loads(ws.recv(timeout=5))
                self.assertEqual(first["type"], "move")
                self.assertEqual(first["move"], "f2f3")
                self.assertEqual(first["state"]["ply"], 1)

                for move in ("e7e5", "g2g4", "d8h4"):
                    fx.post("/move", {"move": move})
                    ws.recv(timeout=5)  # move 消息
                over = json.loads(ws.recv(timeout=5))
                self.assertEqual(over["type"], "game_over")
                self.assertEqual(over["reason"], "checkmate")
                self.assertEqual(over["result"], "0-1")

    def test_ping_pong(self):
        with ServerFixture("human", "human") as fx:
            with connect(fx.ws) as ws:
                json.loads(ws.recv(timeout=5))  # hello
                ws.send(json.dumps({"type": "ping"}))
                pong = json.loads(ws.recv(timeout=5))
                self.assertEqual(pong["type"], "pong")


class TestUiAssets(unittest.TestCase):
    def test_index_and_assets(self):
        with ServerFixture("human", "builtin:greedy") as fx:
            with urllib.request.urlopen(fx.base + "/", timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                self.assertIn("text/html", resp.headers.get("Content-Type", ""))
                html = resp.read().decode("utf-8")
            self.assertIn("ChessArena", html)
            self.assertIn("/ui/app.js", html)
            self.assertIn("chessground", html)

            for path in (
                "/ui/app.js",
                "/ui/style.css",
                "/vendor/chessground/dist/chessground.min.js",
                "/vendor/chessground/assets/chessground.base.css",
            ):
                with urllib.request.urlopen(fx.base + path, timeout=5) as resp:
                    self.assertEqual(resp.status, 200, msg=path)
                    self.assertTrue(resp.read(), msg=path)

    def test_snapshot_has_ui_fields(self):
        # 双方都是人类：没有 AI 抢先应手，断言不会被时序干扰
        with ServerFixture("human", "human") as fx:
            _, state = fx.get("/state")
            for key in ("history_san", "captured", "human", "paused", "speed",
                        "timeout", "start_fen", "last_move"):
                self.assertIn(key, state, msg=key)
            self.assertEqual(state["human"], {"w": True, "b": True})
            self.assertEqual(state["history_san"], [])
            fx.post("/move", {"move": "e2e4"})
            _, state = fx.get("/state")
            self.assertEqual(state["history_san"], ["e4"])
            self.assertEqual(state["last_move"], "e2e4")


class TestControlExtra(unittest.TestCase):
    def test_new_with_players_switches_to_ava(self):
        with ServerFixture("human", "builtin:greedy") as fx:
            status, body = fx.post(
                "/control",
                {"action": "new", "white": "builtin:random", "black": "builtin:random"},
            )
            self.assertEqual(status, 200)
            self.assertEqual(body["state"]["human"], {"w": False, "b": False})
            status, body = fx.post("/move", {"move": "e2e4"})
            self.assertEqual(status, 409)

    def test_undo_in_human_game(self):
        with ServerFixture("human", "builtin:greedy") as fx:
            fx.post("/move", {"move": "e2e4"})
            fx.wait_ply(2)
            status, body = fx.post("/control", {"action": "undo"})
            self.assertEqual(status, 200)
            self.assertEqual(body["state"]["ply"], 0)
            self.assertEqual(body["state"]["turn"], "w")

    def test_resign(self):
        with ServerFixture("human", "builtin:greedy") as fx:
            status, body = fx.post("/control", {"action": "resign"})
            self.assertEqual(status, 200)
            self.assertEqual(body["state"]["over"], True)
            self.assertEqual(body["state"]["result"], "0-1")
            self.assertEqual(body["state"]["over_reason"], "resign")


class TestResilience(unittest.TestCase):
    """针对"AI 回合卡住"加的自愈与可观测性。"""

    def test_debug_reports_driver(self):
        with ServerFixture("human", "builtin:greedy") as fx:
            status, body = fx.get("/debug")
            self.assertEqual(status, 200)
            self.assertTrue(body["driver_alive"])
            self.assertEqual(body["stalls"], 0)
            self.assertIn("game_id", body)

    def test_heartbeat_pushes_state(self):
        with ServerFixture("human", "human") as fx:
            with connect(fx.ws) as ws:
                json.loads(ws.recv(timeout=5))  # hello
                seen = []
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    msg = json.loads(ws.recv(timeout=5))
                    seen.append(msg["type"])
                    if msg["type"] == "heartbeat":
                        self.assertIn("state", msg)
                        break
                self.assertIn("heartbeat", seen)

    def test_driver_restarts_after_death(self):
        with ServerFixture("human", "human") as fx:
            session = fx.session
            session._stop = True
            session._driver.join(timeout=2)
            self.assertFalse(session.driver_alive)
            session._stop = False
            self.assertTrue(session.ensure_driver())
            self.assertTrue(session.driver_alive)

    def test_stall_detected_when_side_has_no_agent(self):
        with ServerFixture("human", None) as fx:
            status, body = fx.post("/move", {"move": "e2e4"})
            self.assertEqual(status, 200, msg=body)
            deadline = time.monotonic() + 5
            stalls = 0
            while time.monotonic() < deadline:
                _, debug = fx.get("/debug")
                stalls = debug["stalls"]
                if stalls:
                    break
                time.sleep(0.05)
            self.assertGreaterEqual(stalls, 1, "没检测到空转")
            self.assertTrue(fx.get("/debug")[1]["driver_alive"])


class TestRecordMode(unittest.TestCase):
    def test_record_writes_jsonl(self):
        # 用工作区内的 runs/ 下临时子目录（沙箱不允许删系统 temp）
        base = Path("runs") / ("test-record-%d" % (__import__("os").getpid(),))
        shutil.rmtree(base, ignore_errors=True)
        try:
            arena = Arena(live=False, record=True, seed=0,
                          config="__no_such_config__.yaml", runs_dir=base)
            try:
                game = arena.new_game(white="builtin:random", black="builtin:greedy")
                game.run_to_end(max_plies=60)
                game_id = game.game_id
            finally:
                arena.close()

            path = base / ("%s.jsonl" % (game_id,))
            self.assertTrue(path.exists(), "录像文件没生成")
            lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertGreater(len(lines), 10)
            self.assertEqual(lines[0]["type"], "move")
            self.assertTrue(all("t" in item for item in lines))
            moves = [item for item in lines if item["type"] == "move"]
            self.assertEqual(len(moves), game.ply)
            if game.over:
                self.assertEqual(lines[-1]["type"], "game_over")
                self.assertEqual(lines[-1]["reason"], game.over_reason)
        finally:
            shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
