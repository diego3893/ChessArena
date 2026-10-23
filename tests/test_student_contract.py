"""学生数据边界、主动submit重试与过期思考保护。"""

import threading
import unittest

import chess

from chessarena import Agent, Arena, NotYourTurnError, RC, State


class TestStudentContract(unittest.TestCase):
    def setUp(self):
        self.arena = Arena(live=False, config="__no_such_config__.yaml")
        self.addCleanup(self.arena.close)

    def test_student_callbacks_receive_only_data_and_player_capability(self):
        seen = []

        class Student(Agent):
            def on_game_start(self, state, color):
                seen.append(state)

            def choose_move(self, state):
                seen.append(state)
                for target in (state, self.game.state, self.game.board):
                    for forbidden in ("legal_moves", "apply", "moves_from", "_b"):
                        self_test.assertFalse(hasattr(target, forbidden))
                for forbidden in ("reset", "undo", "_board", "white", "black"):
                    self_test.assertFalse(hasattr(self.game, forbidden))
                return self.game.submit("e2e4")

        self_test = self
        game = self.arena.new_game(white=Student(), black="builtin:random")
        self.assertTrue(game.step())
        self.assertEqual(game.history, ("e2e4",))
        self.assertEqual(len(seen), 2)
        self.assertTrue(all(isinstance(s, State) for s in seen))

    def test_submit_result_retries_without_double_recording(self):
        class Student(Agent):
            def choose_move(self, state):
                move = "e2e4" if state.last_error else "e2e5"
                return self.game.submit(move)

        game = self.arena.new_game(white=Student(), black="builtin:random")
        self.assertTrue(game.step())
        self.assertEqual(game.history, ("e2e4",))
        self.assertEqual(len(game.rejected), 1)
        self.assertNotIn("可走", game.rejected[0]["reason"])

    def test_late_student_thread_cannot_submit_in_a_later_turn(self):
        release, done = threading.Event(), threading.Event()
        results = []

        class Slow(Agent):
            def choose_move(self, state):
                release.wait(2)
                results.append(self.game.submit("e2e4"))
                results.append(self.game.resign())
                try:
                    self.game.submit("e2e4", strict=True)
                except NotYourTurnError:
                    results.append("strict_rejected")
                done.set()
                return None

        self.addCleanup(release.set)
        arena = Arena(live=False, timeout=0.05, on_timeout="random",
                      config="__no_such_config__.yaml")
        self.addCleanup(arena.close)
        game = arena.new_game(white=Slow(), black="builtin:random")
        self.assertTrue(game.step())
        self.assertTrue(game.step())
        before = game.state
        release.set()
        self.assertTrue(done.wait(1))
        self.assertEqual(results[0], RC.NOT_YOUR_TURN)
        self.assertEqual(results[1], RC.NOT_YOUR_TURN)
        self.assertEqual(results[2], "strict_rejected")
        self.assertEqual(game.state, before)

    def test_complete_position_metadata_and_raw_ep_target(self):
        game = self.arena.new_game(white=None, black=None)
        game.submit("e2e4")
        state = game.state
        self.assertEqual(state.ep_square, "e3")
        self.assertEqual(state.fen.split()[3], "e3")
        self.assertEqual(state.castling_rights, "KQkq")
        self.assertEqual(state.halfmove_clock, 0)
        self.assertEqual(state.fullmove_number, 1)
        self.assertEqual(State.from_json(game.to_json()), state)
        local = chess.Board(state.fen)  # 学生自行使用的规则库
        self.assertEqual(local.turn, chess.BLACK)

    def test_no_early_draw_claim_and_initial_terminal_is_adjudicated(self):
        game = self.arena.new_game(white=None, black=None)
        for move in ("g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1"):
            game.submit(move)
        self.assertFalse(game.state.is_game_over)
        game.submit("f6g8")
        self.assertTrue(game.state.is_game_over)
        terminal = self.arena.new_game(white=None, black=None,
                                       fen="7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
        self.assertTrue(terminal.over)
        self.assertEqual(terminal.over_reason, "stalemate")
