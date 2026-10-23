"""可选PyTorch接入：任意张量形状、学生解码、真实裁判和初始化清理。"""

import importlib.util
import shutil
import unittest
from pathlib import Path

import chess

from chessarena import Arena, RC
from chessarena.core.errors import AgentLoadError
from chessarena.torch_agent import TorchAgent


@unittest.skipUnless(importlib.util.find_spec("torch"), "未安装可选PyTorch依赖")
class TestTorchAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch

        cls.torch = torch
        cls.old_threads = torch.get_num_threads()
        torch.set_num_threads(1)

    @classmethod
    def tearDownClass(cls):
        cls.torch.set_num_threads(cls.old_threads)

    def setUp(self):
        self.arena = Arena(live=False, config="__no_such_config__.yaml")
        self.addCleanup(self.arena.close)

    def student(self, features, outputs):
        torch = self.torch
        test = self

        class Student(TorchAgent):
            def load_model(self):
                self.loads = getattr(self, "loads", 0)+1
                return torch.nn.Linear(features, outputs)

            def encode(self, state):
                test.assertFalse(hasattr(state, "legal_moves"))
                return torch.zeros(1, features, device=self.device)

            def decode(self, output, state):
                test.assertEqual(tuple(output.shape), (1, outputs))
                test.assertTrue(torch.is_inference_mode_enabled())
                test.assertFalse(output.requires_grad)
                moves = sorted(m.uci() for m in chess.Board(state.fen).legal_moves)
                return moves[int(output.argmax().item()) % len(moves)]

        return Student()

    def test_two_different_network_shapes_can_play_without_platform_codec(self):
        white, black = self.student(2, 3), self.student(5, 7)
        self.assertIsNone(white._model)
        game = self.arena.new_game(white=white, black=black)
        self.assertFalse(white._model.training)
        for _ in range(6):
            self.assertTrue(game.step())
        self.assertEqual(game.ply, 6)
        self.assertEqual(game.rejected, [])
        self.assertEqual((white.loads, black.loads), (1, 1))

    def test_adapter_does_not_correct_an_illegal_student_decision(self):
        student = self.student(2, 3)
        student.decode = lambda output, state: "e2e5"
        game = self.arena.new_game(white=student, black="builtin:random", max_retries=1)
        before = game.state.fen
        game.step()
        self.assertEqual(game.state.fen, before)
        self.assertEqual(game.ply, 0)
        self.assertEqual([r["code"] for r in game.rejected], [RC.ILLEGAL_MOVE]*2)
        self.assertEqual(game.over_reason, "retry_exhausted")

    def test_student_checkpoint_loading_and_standalone_inference(self):
        from agents.examples._torch_student import (
            STUDENT_ENCODING, ExampleStudent, build_network,
        )
        from chessarena import State

        base = Path("runs/test-torch-checkpoint")
        base.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(base, ignore_errors=True))
        path = base / "student.pt"
        self.torch.save({"encoding": STUDENT_ENCODING, "hidden": 8,
                         "state_dict": build_network(8).state_dict()}, path)
        student = ExampleStudent()
        student.weights = path
        state = State(chess.Board())
        move = student.decide(state)
        self.assertIn(move, [m.uci() for m in chess.Board(state.fen).legal_moves])
        self.assertEqual(state.ply, 0)
        self.assertIsNone(student.game)
        student.close()
        self.assertIsNone(student._model)

    def test_failed_model_initialization_closes_already_loaded_opponent(self):
        white, black = self.student(2, 3), self.student(3, 4)
        black.load_model = lambda: (_ for _ in ()).throw(ValueError("权重不匹配"))
        with self.assertRaisesRegex(AgentLoadError, "权重不匹配"):
            self.arena.new_game(white=white, black=black)
        self.assertIsNone(white._model)
        self.assertIsNone(black._model)
