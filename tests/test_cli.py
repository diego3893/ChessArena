"""CLI 冒烟：test / league / replay 三条命令能跑通并产出东西。"""

import contextlib
import io
import shutil
import unittest
from pathlib import Path

from chessarena import cli
from chessarena.core.arena import Arena

AGENT = "agents/examples/random_agent.py"


def run(*argv):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        try:
            code = cli.main(list(argv))
        except SystemExit as exc:  # argparse --help 会走这条路
            code = exc.code or 0
    return code, buffer.getvalue()


class TestCli(unittest.TestCase):
    def setUp(self):
        self.out = Path("runs") / "test-cli"
        shutil.rmtree(self.out, ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.out, ignore_errors=True)

    def test_help_lists_commands(self):
        code, out = run("--help")
        self.assertEqual(code, 0)
        for name in ("play", "serve", "test", "league", "replay"):
            self.assertIn(name, out)

    def test_play_writes_pgn(self):
        target = self.out / "one.pgn"
        code, out = run("play", "--white", "builtin:random", "--black", "builtin:random",
                        "--max-plies", "60", "--pgn", str(target), "--quiet")
        self.assertIn(code, (0, 3))
        self.assertTrue(target.exists())
        self.assertIn("结果：", out)

    def test_test_command(self):
        code, out = run("test", AGENT, "--vs", "builtin:random", "--games", "2",
                        "--max-plies", "80")
        self.assertIn(code, (0, 3), msg=out)
        self.assertIn("胜率", out)
        self.assertIn("平均每步", out)

    def test_league_command(self):
        code, out = run("league", "--players", "random,greedy", "--rounds", "1",
                        "--openings", "2", "--concurrent", "1", "--max-plies", "120",
                        "--out", str(self.out))
        self.assertIn(code, (0, 3), msg=out)
        self.assertIn("ELO", out)
        report = self.out / "index.html"
        self.assertTrue(report.exists())
        pgns = list((self.out / "pgn").glob("*.pgn"))
        self.assertEqual(len(pgns), 2)

    def test_replay_command(self):
        target = self.out / "one.pgn"
        run("play", "--max-plies", "60", "--pgn", str(target), "--quiet")
        self.assertTrue(target.exists())
        code, out = run("replay", str(target))
        self.assertEqual(code, 0)
        self.assertIn("结果：", out)

    def test_replay_missing_file(self):
        code, out = run("replay", str(self.out / "nope.pgn"))
        self.assertEqual(code, 2)


class TestAgentsEndpointPayload(unittest.TestCase):
    def test_players_payload_includes_examples_dir_agents(self):
        """agents/ 只扫一层；examples/ 子目录不该被当成选手。"""
        arena = Arena(live=False, config="__no_such_config__.yaml")
        try:
            names = [info.name for info in arena.agents()]
        finally:
            arena.close()
        self.assertNotIn("样例·随机", names)


if __name__ == "__main__":
    unittest.main()
