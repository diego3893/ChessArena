"""阶段 1 内核测试：返回码、原子性、终局、重试预算、事件。

运行：``python -m unittest discover -s tests -t .``
"""

import time
import unittest

import chess

import chessarena
from chessarena import Agent, Arena, RC, uci, square, xy
from chessarena.core.game import START_FEN


class IllegalAgent(Agent):
    name = "总是非法"
    fast_local = True

    def choose_move(self, state):
        return "e2e5"


class NoneAgent(Agent):
    name = "弃权"
    fast_local = True

    def choose_move(self, state):
        return None


class SleepAgent(Agent):
    name = "慢思考"
    fast_local = True

    def choose_move(self, state):
        time.sleep(0.2)
        return sorted(m.uci() for m in chess.Board(state.fen).legal_moves)[0]


class SelfSubmitAgent(Agent):
    """层 2：自己在 choose_move 里落子，然后返回 None。"""

    name = "自己落子"
    fast_local = True

    def choose_move(self, state):
        self.game.submit(sorted(m.uci() for m in chess.Board(state.fen).legal_moves)[0])
        return None


class BoomAgent(Agent):
    name = "会崩"
    fast_local = True

    def choose_move(self, state):
        raise RuntimeError("学生代码写错了")


class SlipperyHuman(Agent):
    """模拟人类手滑：先给两步非法，再给合法。"""

    name = "手滑的人"
    fast_local = True
    is_human = True

    def __init__(self):
        super().__init__()
        self.calls = 0

    def choose_move(self, state):
        self.calls += 1
        if self.calls <= 2:
            return "e2e5"
        return sorted(m.uci() for m in chess.Board(state.fen).legal_moves)[0]


class TestMovesAndResult(unittest.TestCase):
    def test_uci_square_xy(self):
        self.assertEqual(uci(4, 1, 4, 3), "e2e4")
        self.assertEqual(uci(4, 6, 4, 7, "q"), "e7e8q")
        self.assertEqual(square(0, 0), "a1")
        self.assertEqual(xy("e2"), (4, 1))
        with self.assertRaises(ValueError):
            square(8, 0)

    def test_result_semantics(self):
        ok = chessarena.Result(RC.OK, "ok", "e2e4")
        self.assertTrue(ok)
        self.assertEqual(ok, 0)
        bad = chessarena.Result(RC.ILLEGAL_MOVE, "非法着法：e2 的兵不能走到 e5")
        self.assertFalse(bad)
        self.assertEqual(bad, -1)
        self.assertIn("非法", bad.reason)


class TestSubmitCodes(unittest.TestCase):
    def setUp(self):
        self.arena = Arena(live=False, seed=0, config="__no_such_config__.yaml")
        self.game = self.arena.new_game(white="builtin:random", black="builtin:random")

    def tearDown(self):
        self.arena.close()

    def test_ok_and_history(self):
        r = self.game.submit("e2e4")
        self.assertTrue(r)
        self.assertEqual(self.game.history, ("e2e4",))
        self.assertEqual(self.game.ply, 1)
        self.assertEqual(self.game.turn, "b")

    def test_bad_format(self):
        for move in ("Nf3", "E2E4", "e2-e4", "e9e4", "e2e4k", "", None, 42):
            before = self.game.state
            r = self.game.submit(move)
            self.assertEqual(r, RC.BAD_FORMAT, msg="move=%r" % (move,))
            self.assertEqual(self.game.state.fen, before.fen)
            self.assertEqual(self.game.ply, 0)

    def test_illegal(self):
        before = self.game.state
        r = self.game.submit("e2e5")
        self.assertEqual(r, RC.ILLEGAL_MOVE)
        self.assertIn("e2", r.reason)
        self.assertEqual(self.game.state.fen, before.fen)
        self.assertEqual(self.game.ply, 0)
        self.assertIsNotNone(self.game.state.last_error)

    def test_not_your_turn(self):
        with self.game.acting_as("b"):
            r = self.game.submit("e2e4")
        self.assertEqual(r, RC.NOT_YOUR_TURN)
        self.assertEqual(self.game.ply, 0)

    def test_game_over_code(self):
        for move in ("f2f3", "e7e5", "g2g4", "d8h4"):
            self.assertTrue(self.game.submit(move), msg=move)
        self.assertTrue(self.game.over)
        r = self.game.submit("a2a3")
        self.assertEqual(r, RC.GAME_OVER)

    def test_atomicity_after_rejection(self):
        self.game.submit("e2e4")
        snapshot = self.game.state
        for move in ("Nf3", "e2e4", "a2a3"):
            self.assertFalse(self.game.submit(move).ok, msg=move)  # 全部应被拒
        after = self.game.state
        self.assertEqual(after.fen, snapshot.fen)
        self.assertEqual(after.history, snapshot.history)
        self.assertEqual(after.ply, snapshot.ply)

    def test_strict_raises(self):
        with self.assertRaises(chessarena.IllegalMoveError):
            self.game.submit("e2e5", strict=True)
        with self.assertRaises(chessarena.GameOverError):
            for move in ("f2f3", "e7e5", "g2g4", "d8h4"):
                self.game.submit(move)
            self.game.submit("a2a3", strict=True)

    def test_resign(self):
        r = self.game.resign("w")
        self.assertTrue(r)
        self.assertEqual(self.game.result, "0-1")
        self.assertEqual(self.game.over_reason, "resign")

    def test_undo(self):
        self.game.submit("e2e4")
        self.game.submit("e7e5")
        self.assertTrue(self.game.undo(1))
        self.assertEqual(self.game.ply, 1)
        self.assertEqual(self.game.turn, "b")

    def test_reset(self):
        self.game.submit("e2e4")
        self.game.reset()
        self.assertEqual(self.game.ply, 0)
        self.assertEqual(self.game.state.fen, START_FEN)

    def test_state_is_data_only_and_immutable(self):
        state = self.game.state
        for name in ("legal_moves", "apply", "_b"):
            self.assertFalse(hasattr(state, name))
        with self.assertRaises(AttributeError):
            state.turn = "b"
        self.game.submit("e2e4")
        self.assertEqual(state.fen, START_FEN)
        self.assertEqual(self.game.state.ep_square, "e3")
        self.assertEqual(self.game.state.castling_rights, "KQkq")

    def test_board_is_readonly(self):
        board = self.game.board
        self.assertEqual(board.piece_at("e2"), "P")
        self.assertEqual(board.turn, "w")
        self.assertFalse(hasattr(board, "moves_from"))
        self.assertEqual(len(board.matrix()), 8)
        with self.assertRaises(AttributeError):
            board.fen = "8/8/8/8/8/8/8/8 w - - 0 1"

    def test_board_cannot_leak_referee_position(self):
        board = self.game.board
        self.assertFalse(hasattr(board, "_b"))
        matrix = board.matrix()
        matrix[6][4] = "Q"
        self.assertEqual(self.game.state.fen, START_FEN)
        self.assertEqual(self.game.ply, 0)
        self.assertEqual(board.piece_at("e2"), "P")
        self.game.submit("e2e4")
        self.assertEqual(board.piece_at("e4"), "P")
        self.game.reset()
        self.assertEqual(board.piece_at("e2"), "P")
        self.assertEqual(board.piece_at("e4"), ".")

    def test_snapshots_do_not_share_input_board(self):
        source = chess.Board()
        state = chessarena.State(source)
        board = chessarena.Board(source)
        source.clear()
        self.assertEqual(state.fen, START_FEN)
        self.assertEqual(board.fen, START_FEN)
        self.assertEqual(state.fen, START_FEN)

    def test_no_action_space_in_public_views(self):
        for obj in (self.game.state, self.game.board, self.game.player("w")):
            for name in ("legal_moves", "moves_from", "apply"):
                self.assertFalse(hasattr(obj, name))
        for name in ("reset", "undo", "step", "acting_as", "_board"):
            self.assertFalse(hasattr(self.game.player("w"), name))


class TestTerminal(unittest.TestCase):
    def setUp(self):
        self.arena = Arena(live=False, seed=0, config="__no_such_config__.yaml")

    def tearDown(self):
        self.arena.close()

    def _game(self, fen=None, white="builtin:random", black="builtin:random"):
        return self.arena.new_game(white=white, black=black, fen=fen)

    def test_checkmate(self):
        g = self._game()
        for move in ("f2f3", "e7e5", "g2g4", "d8h4"):
            r = g.submit(move)
            self.assertTrue(r, msg="%s: %s" % (move, r.reason))
        self.assertEqual(g.over_reason, "checkmate")
        self.assertEqual(g.result, "0-1")

    def test_stalemate(self):
        g = self._game(fen="7k/8/4Q1K1/8/8/8/8/8 w - - 0 1")
        self.assertTrue(g.submit("e6f7"))
        self.assertEqual(g.over_reason, "stalemate")
        self.assertEqual(g.result, "1/2-1/2")

    def test_insufficient_material(self):
        g = self._game(fen="8/8/8/8/8/2b5/6k1/KN6 w - - 0 1")
        self.assertTrue(g.submit("b1c3"))
        self.assertEqual(g.over_reason, "insufficient")
        self.assertEqual(g.result, "1/2-1/2")

    def test_fifty_moves(self):
        g = self._game(fen="8/8/8/8/8/8/6k1/KR6 w - - 99 60")
        self.assertTrue(g.submit("b1b2"))
        self.assertEqual(g.over_reason, "fifty")
        self.assertEqual(g.result, "1/2-1/2")

    def test_threefold(self):
        g = self._game()
        cycle = ("g1f3", "g8f6", "f3g1", "f6g8")
        for _ in range(2):
            for move in cycle:
                self.assertTrue(g.submit(move), msg=move)
        self.assertEqual(g.over_reason, "threefold")
        self.assertEqual(g.result, "1/2-1/2")


class TestDriving(unittest.TestCase):
    def setUp(self):
        self.arena = Arena(live=False, seed=0, config="__no_such_config__.yaml")

    def tearDown(self):
        self.arena.close()

    def test_run_to_end_random_vs_greedy(self):
        g = self.arena.new_game(white="builtin:random", black="builtin:greedy")
        g.run_to_end(max_plies=400)
        self.assertTrue(g.over)
        self.assertGreater(g.ply, 4)
        self.assertIn("[Result", g.pgn())

    def test_retry_exhausted_forfeits(self):
        g = self.arena.new_game(white=IllegalAgent(), black="builtin:random", max_retries=1)
        g.step()
        self.assertTrue(g.over)
        self.assertEqual(g.over_reason, "retry_exhausted")
        self.assertEqual(g.result, "0-1")
        self.assertEqual(len(g.rejected), 2)  # 1 次 + 1 次重试

    def test_retry_random_policy_continues(self):
        arena = Arena(
            live=False,
            seed=0,
            config="__no_such_config__.yaml",
            on_retry_exhausted="random",
        )
        g = arena.new_game(white=IllegalAgent(), black="builtin:random", max_retries=0)
        try:
            g.step()
            self.assertFalse(g.over)
            self.assertEqual(g.ply, 1)
        finally:
            arena.close()

    def test_timeout_forfeits(self):
        g = self.arena.new_game(white=SleepAgent(), black="builtin:random", timeout=0.05)
        g.step()
        self.assertTrue(g.over)
        self.assertEqual(g.over_reason, "timeout")
        self.assertEqual(g.result, "0-1")

    def test_none_forfeits(self):
        g = self.arena.new_game(white=NoneAgent(), black="builtin:random")
        g.step()
        self.assertTrue(g.over)
        self.assertEqual(g.over_reason, "forfeit")

    def test_exception_forfeits(self):
        g = self.arena.new_game(white=BoomAgent(), black="builtin:random")
        g.step()
        self.assertTrue(g.over)
        self.assertEqual(g.over_reason, "error")

    def test_layer2_self_submit_is_not_double_played(self):
        g = self.arena.new_game(white=SelfSubmitAgent(), black="builtin:random")
        g.step()
        self.assertEqual(g.ply, 1)
        self.assertFalse(g.over)

    def test_human_rejections_do_not_consume_retries(self):
        g = self.arena.new_game(white=SlipperyHuman(), black="builtin:random", max_retries=0)
        g.step()
        self.assertFalse(g.over)
        self.assertEqual(g.ply, 1)
        self.assertEqual(len(g.rejected), 2)

    def test_events(self):
        g = self.arena.new_game(white="builtin:random", black="builtin:random")
        seen = []
        g.on("move", lambda move, result: seen.append(("move", move)))
        g.on("illegal", lambda move, result: seen.append(("illegal", result.code)))
        g.on("game_over", lambda result, reason: seen.append(("over", reason)))
        g.submit("e2e5")
        g.submit("e2e4")
        self.assertEqual(seen[0], ("illegal", RC.ILLEGAL_MOVE))
        self.assertEqual(seen[1], ("move", "e2e4"))

    def test_to_json(self):
        g = self.arena.new_game(white="builtin:random", black="builtin:random")
        g.submit("e2e4")
        payload = g.to_json()
        self.assertEqual(payload["turn"], "b")
        self.assertEqual(payload["history"], ["e2e4"])
        self.assertEqual(payload["history_san"], ["e4"])
        self.assertEqual(payload["last_move"], "e2e4")
        self.assertEqual(payload["captured"], {"w": [], "b": []})
        self.assertFalse(payload["over"])

    def test_throughput(self):
        g = self.arena.new_game(white="builtin:random", black="builtin:random")
        started = time.monotonic()
        plies = 0
        while not g.over and plies < 60:
            g.step()
            plies += 1
        elapsed = max(1e-6, time.monotonic() - started)
        self.assertGreater(plies / elapsed, 200.0, "吞吐过低：%.0f plies/s" % (plies / elapsed,))

    def test_pgn_roundtrip(self):
        g = self.arena.new_game(white="builtin:random", black="builtin:greedy")
        g.run_to_end(max_plies=60)
        pgn = g.pgn()
        parsed = chess.pgn.read_game(__import__("io").StringIO(pgn))
        self.assertIsNotNone(parsed)
        self.assertEqual(len(list(parsed.mainline_moves())), g.ply)


if __name__ == "__main__":
    unittest.main()
