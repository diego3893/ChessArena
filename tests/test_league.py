"""阶段 5 测试：联赛编排、ELO、报告、断点续跑。"""

import json
import shutil
import unittest
from pathlib import Path

from chessarena.league import League, compute_ratings, expected_score, score_of


class TestElo(unittest.TestCase):
    def test_score_of(self):
        self.assertEqual(score_of("1-0", "w"), 1.0)
        self.assertEqual(score_of("1-0", "b"), 0.0)
        self.assertEqual(score_of("1/2-1/2", "w"), 0.5)
        self.assertIsNone(score_of("*", "b"))

    def test_expected_score(self):
        self.assertAlmostEqual(expected_score(1500, 1500), 0.5)
        self.assertGreater(expected_score(1800, 1500), 0.5)
        self.assertLess(expected_score(1200, 1500), 0.5)

    def test_compute_ratings(self):
        records = [
            {"white": "A", "black": "B", "result": "1-0"},
            {"white": "B", "black": "A", "result": "0-1"},
        ]
        ratings = compute_ratings(records)
        self.assertGreater(ratings["A"], 1500)
        self.assertLess(ratings["B"], 1500)
        # 两连胜的总分应该等于两连败的总分（零和）
        self.assertAlmostEqual(ratings["A"] + ratings["B"], 3000.0, places=6)


class TestLeague(unittest.TestCase):
    def setUp(self):
        self.out = Path("runs") / "test-league"
        shutil.rmtree(self.out, ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.out, ignore_errors=True)

    def _league(self, **kwargs):
        opts = dict(rounds=1, openings=4, max_concurrent=1, seed=0,
                    timeout=2.0, max_plies=160, config="__no_such_config__.yaml")
        opts.update(kwargs)
        return League(["builtin:random", "builtin:greedy"], **opts)

    def test_runs_and_reports(self):
        result = self._league().run(self.out, resume=False)
        self.assertEqual(len(result.records), 2)          # 1 轮 × 一对 × 黑白各一
        self.assertEqual({r["white"] for r in result.records},
                         {"builtin:random", "builtin:greedy"})
        self.assertEqual(len(result.rows), 2)
        self.assertTrue(result.report_path.exists())
        html = result.report_path.read_text(encoding="utf-8")
        self.assertIn("ELO", html)
        self.assertIn("非法率", html)
        self.assertEqual(len(list(result.pgn_dir.glob("*.pgn"))), 2)
        for row in result.rows:
            self.assertIn("elo", row)
            self.assertIn("illegal_rate", row)
            self.assertGreaterEqual(row["games"], 1)

    def test_resume_skips_finished_games(self):
        league = self._league()
        league.run(self.out, resume=False)
        log = self.out / "games.jsonl"
        first = len(log.read_text(encoding="utf-8").splitlines())
        self.assertEqual(first, 2)
        league.run(self.out, resume=True)
        second = len(log.read_text(encoding="utf-8").splitlines())
        self.assertEqual(second, first, "续跑不该重复写已完成的对局")

    def test_schedule_orders(self):
        jobs = self._league(rounds=2).schedule()
        self.assertEqual(len(jobs), 4)  # 2 轮 × 每对 2 局（黑白各一）
        pairs = {(job["white"], job["black"]) for job in jobs}
        self.assertIn(("builtin:random", "builtin:greedy"), pairs)
        self.assertIn(("builtin:greedy", "builtin:random"), pairs)
        self.assertEqual([job["idx"] for job in jobs], list(range(len(jobs))))

    def test_report_contains_players(self):
        result = self._league().run(self.out, resume=False)
        html = result.report_path.read_text(encoding="utf-8")
        self.assertIn("builtin:random", html)
        self.assertIn("builtin:greedy", html)
        ratings = json.loads((self.out / "ratings.json").read_text(encoding="utf-8"))
        self.assertEqual(set(ratings["ratings"]), {"builtin:random", "builtin:greedy"})


if __name__ == "__main__":
    unittest.main()
