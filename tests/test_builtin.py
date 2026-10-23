"""阶段 4 测试：五档内置、L3/L4 战术与耗时、Stockfish 冒烟。"""

import time
import unittest

import chess

from chessarena import Arena
from chessarena.builtin import available, make_builtin
from chessarena.builtin.evaluation import evaluate
from chessarena.core.state import State
from chessarena.engines.uci import UCIEngine
from chessarena.core.errors import EngineError

MATE_IN_1 = "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5Q2/PPPP1PPP/RNB1K1NR w KQkq - 4 4"
MIDGAME = "r1bq1rk1/pp2bppp/2n1pn2/3p4/3P4/2N1PN2/PP1BBPPP/R2Q1RK1 w - - 0 10"
POSITIONS = (chess.STARTING_FEN, MIDGAME, MATE_IN_1)


def state_of(fen):
    return State(chess.Board(fen))


class TestRegistry(unittest.TestCase):
    def test_five_builtins(self):
        self.assertEqual(available(), ["random", "greedy", "minimax2", "minimax3", "stockfish"])

    def test_arena_lists_five(self):
        arena = Arena(live=False, config="__no_such_config__.yaml")
        try:
            self.assertEqual(arena.builtins(), available())
        finally:
            arena.close()

    def test_unknown_builtin_raises(self):
        with self.assertRaises(KeyError):
            make_builtin("nope")


class TestEvaluation(unittest.TestCase):
    def test_material_sign(self):
        board = chess.Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
        self.assertEqual(evaluate(board), 0)
        board = chess.Board("4k3/8/8/8/8/8/8/Q3K3 w - - 0 1")  # 白多一个后
        self.assertGreater(evaluate(board), 800)
        board = chess.Board("q3k3/8/8/8/8/8/8/4K3 w - - 0 1")  # 黑多一个后
        self.assertLess(evaluate(board), -800)

    def test_checkmate_score(self):
        # 白方被将杀（愚人杀终局）
        board = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
        self.assertTrue(board.is_checkmate())
        self.assertLess(evaluate(board), -1000)


class TestSearchAgents(unittest.TestCase):
    def test_find_mate_in_one(self):
        for name in ("minimax2", "minimax3"):
            agent = make_builtin(name)
            state = state_of(MATE_IN_1)
            started = time.monotonic()
            move = agent.choose_move(state)
            elapsed = time.monotonic() - started
            self.assertEqual(move, "f3f7", msg="%s 没找到 Qxf7#" % (name,))
            self.assertLess(elapsed, 2.0, msg="%s 超时 %.2fs" % (name, elapsed))

    def test_legal_on_positions(self):
        for name in ("minimax2", "minimax3", "greedy", "random"):
            agent = make_builtin(name)
            for fen in POSITIONS:
                state = state_of(fen)
                move = agent.choose_move(state)
                self.assertIn(move, state.legal_moves, msg="%s @ %s" % (name, fen))

    def test_l4_respects_budget(self):
        agent = make_builtin("minimax3")
        agent.budget = 0.25
        state = state_of(MIDGAME)
        started = time.monotonic()
        move = agent.choose_move(state)
        elapsed = time.monotonic() - started
        self.assertIn(move, state.legal_moves)
        self.assertLess(elapsed, 1.5, "预算 0.25s 却用了 %.2fs" % (elapsed,))

    def test_no_moves_returns_none(self):
        from chessarena.builtin.minimax2 import Minimax2Agent

        agent = Minimax2Agent()
        state = state_of("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")  # 黑方无着可走
        self.assertIsNone(agent.choose_move(state))


class TestStockfish(unittest.TestCase):
    def test_agent_defaults(self):
        agent = make_builtin("stockfish")
        try:
            self.assertEqual(agent.elo, 2600)
            self.assertAlmostEqual(agent.movetime, 1.0)
        finally:
            agent.close()

    def test_config_overrides_default(self):
        agent = make_builtin("stockfish", stockfish={"elo": 1800, "movetime": 0.5})
        try:
            self.assertEqual(agent.elo, 1800)
            self.assertAlmostEqual(agent.movetime, 0.5)
        finally:
            agent.close()

    def test_env_overrides_config(self):
        import os
        from unittest import mock

        with mock.patch.dict(os.environ, {"CHESSARENA_STOCKFISH_ELO": "2600",
                                          "CHESSARENA_STOCKFISH_MOVETIME": "0.3"}):
            agent = make_builtin("stockfish", stockfish={"elo": 1800, "movetime": 0.5})
            try:
                self.assertEqual(agent.elo, 2600)
                self.assertAlmostEqual(agent.movetime, 0.3)
            finally:
                agent.close()

    def test_arena_passes_config(self):
        import shutil
        from pathlib import Path

        base = Path("runs") / "test-sf-config"
        shutil.rmtree(base, ignore_errors=True)
        base.mkdir(parents=True)
        cfg = base / "config.yaml"
        cfg.write_text("stockfish:\n  elo: 2500\n  movetime: 0.4\n", encoding="utf-8")
        arena = Arena(live=False, config=cfg)
        try:
            game = arena.new_game(white="builtin:random", black="builtin:stockfish")
            self.assertEqual(game.black.elo, 2500)
            self.assertAlmostEqual(game.black.movetime, 0.4)
        finally:
            arena.close()
            shutil.rmtree(base, ignore_errors=True)

    def test_engine_returns_legal_move(self):
        engine = UCIEngine(movetime=0.2)
        try:
            move = engine.best_move(chess.STARTING_FEN)
        except EngineError as exc:
            self.skipTest("本机/沙箱无法启动引擎：%s" % (exc,))
        else:
            self.assertIn(move, [m.uci() for m in chess.Board().legal_moves])
        finally:
            engine.close()


if __name__ == "__main__":
    unittest.main()
