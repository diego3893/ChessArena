"""训练与参赛链路的边界回归：提交、回调、重置、计时和模型更新。"""

import importlib.util
import threading
import unittest

import chess

from chessarena import Agent, Arena, RC


class TestRefereeRegressions(unittest.TestCase):
    def setUp(self):
        self.arena = Arena(live=False, config="__missing_config__.yaml")
        self.addCleanup(self.arena.close)

    def test_same_square_returns_bad_format_without_mutation(self):
        game = self.arena.new_game(white=None, black=None)
        for move in ("e2e2", "e1e1", "a7a7q"):
            self.assertEqual(game.player("w").submit(move).code, RC.BAD_FORMAT)
        self.assertEqual(game.ply, 0)
        self.assertEqual(game.state.fen, chess.STARTING_FEN)

    def test_callback_exceptions_do_not_change_mate_or_result(self):
        ended = []

        class BrokenHook(Agent):
            def on_opponent_move(self, move):
                raise ValueError("opponent hook")

            def on_game_end(self, result):
                ended.append(result)
                raise RuntimeError("end hook")

        game = self.arena.new_game(white=BrokenHook(), black=BrokenHook())
        for move in ("f2f3", "e7e5", "g2g4", "d8h4"):
            self.assertTrue(game.submit(move))
        self.assertEqual(game.result, "0-1")
        self.assertEqual(game.over_reason, "checkmate")
        self.assertEqual(ended, ["0-1", "0-1"])
        self.assertEqual(game.resign("b"), RC.GAME_OVER)
        self.assertEqual(game.result, "0-1")

    def test_successful_submit_survives_later_exception(self):
        class Student(Agent):
            fast_local = True

            def choose_move(self, state):
                self.game.submit("e2e4")
                raise ValueError("after submission")

        game = self.arena.new_game(white=Student(), black="builtin:random")
        self.assertTrue(game.step())
        self.assertFalse(game.over)
        self.assertEqual(game.history, ("e2e4",))

    def test_agent_can_resign_without_moving(self):
        class Student(Agent):
            def choose_move(self, state):
                self.game.resign()

        game = self.arena.new_game(white=Student(), black="builtin:random")
        self.assertEqual(game.step().code, RC.GAME_OVER)
        self.assertEqual(game.result, "0-1")
        self.assertEqual(game.over_reason, "resign")
        self.assertEqual(game.ply, 0)

    def test_submit_finishes_turn_without_waiting_for_student_return(self):
        release, done = threading.Event(), threading.Event()
        self.addCleanup(release.set)

        class Student(Agent):
            def choose_move(self, state):
                self.game.submit("e2e4")
                release.wait(2)
                done.set()

        game = self.arena.new_game(white=Student(), black="builtin:random", timeout=0.1)
        try:
            self.assertTrue(game.step())
            self.assertFalse(done.is_set())
            self.assertFalse(game.over)
        finally:
            release.set()
            self.assertTrue(done.wait(1))

    def test_submissions_inside_one_callback_consume_retry_budget(self):
        results = []
        done = threading.Event()

        class Student(Agent):
            def choose_move(self, state):
                for move in ("e2e5", "e2e6", "e2e4"):
                    results.append(self.game.submit(move).code)
                done.set()
                return results[-1]

        game = self.arena.new_game(white=Student(), black="builtin:random", max_retries=1)
        game.step()
        self.assertTrue(done.wait(1))
        self.assertEqual(game.over_reason, "retry_exhausted")
        self.assertEqual(game.ply, 0)
        self.assertEqual(results[:2], [RC.ILLEGAL_MOVE, RC.ILLEGAL_MOVE])
        self.assertIn(results[2], (RC.NOT_YOUR_TURN, RC.GAME_OVER))

    def test_reset_during_thinking_rejects_returned_old_move(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)

        class Student(Agent):
            def choose_move(self, state):
                entered.set()
                release.wait(1)
                return "e2e4"

        game = self.arena.new_game(white=Student(), black="builtin:random")
        results = []
        worker = threading.Thread(target=lambda: results.append(game.step()))
        worker.start()
        try:
            self.assertTrue(entered.wait(1))
            game.reset()
        finally:
            release.set()
            worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(results[0].code, RC.NOT_YOUR_TURN)
        self.assertEqual(game.ply, 0)
        self.assertFalse(game.over)

    def test_invalid_reset_is_atomic_and_valid_reset_clears_rejections(self):
        game = self.arena.new_game(white=None, black=None)
        game.submit("e2e5")
        game.submit("e2e4")
        before = game.state
        with self.assertRaises(ValueError):
            game.reset("8/8/8/8/8/8/8/8 w - - 0 1")
        self.assertEqual(game.state, before)
        game.reset()
        self.assertEqual(game.rejected, [])
        self.assertEqual(game.ply, 0)

    def test_manual_run_does_not_spin_or_forfeit_api_side(self):
        for white in (None, "api"):
            game = self.arena.new_game(white=white, black="builtin:random")
            self.assertIsNone(game.run_to_end())
            self.assertFalse(game.over)
            self.assertEqual(game.ply, 0)

    def test_undo_without_moves_keeps_terminal_result(self):
        game = self.arena.new_game(white=None, black=None,
                                   fen="7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
        self.assertFalse(game.undo())
        self.assertEqual(game.over_reason, "stalemate")

    def test_student_system_exit_is_an_agent_error(self):
        class Student(Agent):
            def choose_move(self, state):
                raise SystemExit(1)

        game = self.arena.new_game(white=Student(), black="builtin:random")
        game.step()
        self.assertEqual(game.over_reason, "error")

    def test_failed_opponent_resolution_closes_first_agent(self):
        closed = []

        class Student(Agent):
            def close(self):
                closed.append(True)

        with self.assertRaises(Exception):
            self.arena.new_game(white=Student(), black="missing-player")
        self.assertEqual(closed, [True])

    def test_game_ids_are_unique(self):
        ids = [self.arena.new_game(white=None, black=None).game_id for _ in range(40)]
        self.assertEqual(len(ids), len(set(ids)))

    def test_configuration_mutations_do_not_leak_between_arenas(self):
        self.arena.config["game"]["timeout"] = 123
        other = Arena(live=False, config="__missing_config__.yaml")
        self.addCleanup(other.close)
        self.assertEqual(other.timeout, 3.0)

    def test_engine_configuration_failure_closes_spawned_process(self):
        from unittest.mock import Mock, patch
        from chessarena.engines.uci import UCIEngine
        from chessarena import EngineError

        engine = Mock()
        engine.configure.side_effect = ValueError("bad option")
        adapter = UCIEngine(options={"Hash": -1})
        with patch("chess.engine.SimpleEngine.popen_uci", return_value=engine):
            with self.assertRaises(EngineError):
                adapter.start()
        engine.quit.assert_called_once()
        self.assertIsNone(adapter._engine)


class TestHttpInputRegressions(unittest.TestCase):
    def test_invalid_uci_and_invalid_position_are_business_errors(self):
        from tests.test_server import ServerFixture

        with ServerFixture("api", "api") as fx:
            status, body = fx.post("/move", {"move": "e2e2", "side": "w"})
            self.assertEqual(status, 400)
            self.assertEqual(body["result"]["code"], RC.BAD_FORMAT)
            for fen in (42, "8/8/8/8/8/8/8/8 w - - 0 1"):
                status, body = fx.post("/reset", {"fen": fen})
                self.assertEqual(status, 400)
                self.assertEqual(body["state"]["ply"], 0)
                self.assertEqual(body["state"]["fen"], chess.STARTING_FEN)


class TestScoringRegressions(unittest.TestCase):
    def test_unfinished_games_do_not_change_elo_or_count_as_draws(self):
        from chessarena.league import compute_ratings, summarize

        records = [{"white": "A", "black": "B", "result": "1-0"}]
        before = compute_ratings(records)
        records.append({"white": "A", "black": "B", "result": "*"})
        self.assertEqual(compute_ratings(records), before)
        rows = {r["name"]: r for r in summarize(records, before)}
        self.assertEqual(rows["A"]["wins"], 1)
        self.assertEqual(rows["A"]["draws"], 0)
        self.assertEqual(rows["A"]["unfinished"], 1)
        self.assertEqual(rows["A"]["win_rate"], 100)

    def test_illegal_moves_are_attributed_to_the_actual_player(self):
        from chessarena.league import play_game, summarize
        from unittest.mock import patch

        class Bad(Agent):
            def choose_move(self, state):
                return "e2e5"

        def resolve(spec, **kwargs):
            from chessarena.builtin.random_agent import RandomAgent
            return Bad() if spec == "bad" else RandomAgent()

        with patch("chessarena.core.arena.resolve_player", side_effect=resolve):
            record = play_game({"idx": 0, "white": "bad", "black": "good", "max_retries": 0})
        self.assertEqual(record["result"], "0-1")
        self.assertEqual(record["player_stats"]["w"]["rejected"], 1)
        self.assertEqual(record["player_stats"]["b"]["rejected"], 0)
        rows = {r["name"]: r for r in summarize([record], {})}
        self.assertEqual(rows["bad"]["illegal_rate"], 100)
        self.assertEqual(rows["good"]["illegal_rate"], 0)

    def test_cli_reports_unfinished_without_loss_and_nonzero_exit(self):
        from tests.test_cli import run

        code, text = run("test", "agents/examples/random_agent.py", "--vs", "builtin:random",
                         "--games", "1", "--max-plies", "1")
        self.assertEqual(code, 3)
        self.assertIn("0 胜 0 和 0 负", text)
        self.assertIn("未完成 1 局", text)

    def test_no_resume_replaces_old_game_log(self):
        from chessarena.league import League
        import json
        from pathlib import Path

        output = Path("runs/test-regression-league")
        league = League(["builtin:random", "builtin:greedy"], rounds=1,
                        openings=0, max_concurrent=1, max_plies=1)
        league.run(output, resume=False)
        result = league.run(output, resume=False)
        records = [json.loads(line) for line in (output/"games.jsonl").read_text().splitlines()]
        self.assertEqual(len(records), 2)
        self.assertTrue(all(r["unfinished"] == 2 for r in result.rows))


@unittest.skipUnless(importlib.util.find_spec("torch"), "PyTorch为可选依赖")
class TestTrainingRoundtrip(unittest.TestCase):
    def test_structured_network_input_and_output_are_student_defined(self):
        import torch
        from chessarena.torch_agent import TorchAgent

        class Network(torch.nn.Module):
            def forward(self, features, bias):
                return {"policy": features[:, :2]+bias}

        class Student(TorchAgent):
            def load_model(self):
                return Network()

            def encode(self, state):
                return {"features": torch.zeros(1, 3, device=self.device),
                        "bias": torch.ones(1, 1, device=self.device)}

            def predict(self, encoded):
                return self._model(**encoded)

            def decode(self, output, state):
                assert output["policy"].shape == (1, 2)
                assert torch.is_inference_mode_enabled()
                return sorted(m.uci() for m in chess.Board(state.fen).legal_moves)[0]

        arena = Arena(live=False)
        self.addCleanup(arena.close)
        game = arena.new_game(white=Student(), black="builtin:random")
        self.assertTrue(game.step())
        self.assertEqual(game.ply, 1)

    def test_platform_samples_support_backward_and_trained_model_can_compete(self):
        import torch
        from agents.examples._torch_student import (
            ExampleStudent, STUDENT_ENCODING, action_index, build_network, encode_position,
        )
        from pathlib import Path

        old_threads = torch.get_num_threads()
        torch.set_num_threads(1)
        self.addCleanup(torch.set_num_threads, old_threads)
        arena = Arena(live=False)
        self.addCleanup(arena.close)
        game = arena.new_game(white=None, black="builtin:random")
        player = game.player("w")
        inputs, labels = [], []
        for _ in range(3):
            state = player.state
            move = sorted(m.uci() for m in chess.Board(state.fen).legal_moves)[0]
            inputs.append(encode_position(state))
            labels.append(action_index(move))
            self.assertTrue(player.submit(move))
            self.assertTrue(game.step())
        torch.manual_seed(11)
        model = build_network(8).train()
        before = model[1].weight.detach().clone()
        optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
        optimizer.zero_grad()
        loss = torch.nn.functional.cross_entropy(model(torch.cat(inputs)), torch.tensor(labels))
        loss.backward()
        self.assertTrue(torch.isfinite(model[1].weight.grad).all())
        optimizer.step()
        self.assertFalse(torch.equal(before, model[1].weight))
        path = Path("runs/test-trained-roundtrip.pt")
        path.parent.mkdir(exist_ok=True)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        torch.save({"encoding": STUDENT_ENCODING, "hidden": 8, "state_dict": model.state_dict()}, path)
        student = ExampleStudent()
        student.weights = path
        match = arena.new_game(white=student, black="builtin:random")
        for _ in range(6):
            if match.over:
                break
            self.assertTrue(match.step())
        self.assertEqual(match.rejected, [])
        self.assertGreaterEqual(match.ply, 4)
