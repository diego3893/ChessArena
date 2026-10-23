"""文档契约：学生 API 文档里写的成员必须真实存在。

学生照着 `docs/chessarena-学生API.md` 写代码，所以这份测试专门盯"文档写了但代码没有"
（或反过来改了名）的漂移。
"""

import unittest

import chess

import chessarena
from chessarena import Agent, Board, Client, Game, Result, RC, State
from chessarena.core.agent import AgentInfo


class TestStudentApiSurface(unittest.TestCase):
    def test_agent_members(self):
        for name in ("name", "choose_move", "on_game_start", "on_game_end", "on_opponent_move"):
            self.assertTrue(hasattr(Agent, name), msg=name)
        agent = Agent()
        for attr in ("game", "color", "seed"):
            self.assertTrue(hasattr(agent, attr), msg=attr)

    def test_state_members(self):
        state = State(chess.Board())
        for attr in ("fen", "turn", "board", "castling_rights", "ep_square", "history", "ply", "is_check",
                     "is_game_over", "result", "last_error"):
            self.assertTrue(hasattr(state, attr), msg=attr)
        for method in ("pretty", "copy"):
            self.assertTrue(callable(getattr(state, method)), msg=method)
        self.assertEqual(state.turn, "w")
        self.assertFalse(hasattr(state, "legal_moves"))
        self.assertFalse(hasattr(state, "apply"))
        self.assertEqual(len(state.board), 8)
        self.assertEqual(len(state.board[0]), 8)
        self.assertTrue(state.pretty())
        self.assertIs(state.copy(), state)

    def test_board_members(self):
        board = Board(chess.Board())
        for attr in ("fen", "turn", "is_check", "matrix", "ascii"):
            self.assertTrue(hasattr(board, attr), msg=attr)
        for method in ("get", "piece_at", "is_empty"):
            self.assertTrue(callable(getattr(board, method)), msg=method)
        self.assertEqual(board.piece_at("e2"), "P")
        self.assertEqual(board.get(4, 1), "P")
        self.assertFalse(hasattr(board, "moves_from"))
        self.assertTrue(board.is_empty(4, 3))

    def test_game_members(self):
        arena = chessarena.Arena(live=False, config="__no_such_config__.yaml")
        try:
            game = arena.new_game(white="builtin:random", black="builtin:random")
            for attr in ("state", "board", "turn", "over", "result", "over_reason",
                         "history", "ply", "white", "black", "game_id"):
                self.assertTrue(hasattr(game, attr), msg=attr)
            for method in ("submit", "resign", "undo", "reset", "wait_my_turn", "on",
                           "clock", "pgn", "step", "run_to_end"):
                self.assertTrue(callable(getattr(game, method)), msg=method)
            self.assertTrue(game.submit("e2e4").ok)
            self.assertEqual(game.state.last_error, None)
        finally:
            arena.close()

    def test_result_members_and_codes(self):
        result = Result(RC.OK, "ok", "e2e4")
        self.assertTrue(result.ok)
        self.assertTrue(result)
        self.assertEqual(result, 0)
        for code in (0, -1, -2, -3, -4):
            self.assertIsInstance(code, int)
        self.assertEqual(RC.ILLEGAL_MOVE, -1)
        self.assertEqual(RC.BAD_FORMAT, -2)
        self.assertEqual(RC.NOT_YOUR_TURN, -3)
        self.assertEqual(RC.GAME_OVER, -4)

    def test_client_members(self):
        client = Client("http://127.0.0.1:1", side="w")
        for method in ("state", "board", "submit", "wait_my_turn", "reset"):
            self.assertTrue(callable(getattr(client, method)), msg=method)
        self.assertEqual(client.side, "w")

    def test_helpers_and_constants(self):
        self.assertEqual(chessarena.uci(4, 1, 4, 3), "e2e4")
        self.assertEqual(chessarena.uci(4, 6, 4, 7, "q"), "e7e8q")
        self.assertEqual(chessarena.square(4, 1), "e2")
        self.assertEqual(chessarena.xy("e2"), (4, 1))
        self.assertIn("8/8", chessarena.START_FEN)

    def test_student_doc_exists_and_lists_core_types(self):
        from pathlib import Path

        doc = Path("docs") / "chessarena-学生API.md"
        self.assertTrue(doc.is_file())
        text = doc.read_text(encoding="utf-8")
        for token in ("Agent", "State", "Result", "Game", "Client", "submit",
                      "legal_moves", "apply", "wait_my_turn"):
            self.assertIn(token, text, msg=token)

    def test_markdown_links_resolve(self):
        """README 与 docs/*.md 里的相对链接必须指向真实文件。"""
        import re
        from pathlib import Path

        root = Path(".")
        files = [root / "README.md"] + sorted((root / "docs").glob("*.md"))
        pattern = re.compile(r"\]\(([^)#]+\.md)(?:#[^)]*)?\)")
        for path in files:
            text = path.read_text(encoding="utf-8")
            for target in pattern.findall(text):
                resolved = (path.parent / target).resolve()
                self.assertTrue(resolved.exists(), msg="%s -> %s" % (path, target))

    def test_agent_info_shape(self):
        info = AgentInfo(name="x", path="agents/x.py", class_name="X", spec="agents/x.py")
        self.assertEqual(info.spec, "agents/x.py")
        self.assertEqual(str(info), "agents/x.py")


if __name__ == "__main__":
    unittest.main()
