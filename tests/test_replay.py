"""PGN回放解析、记录目录边界与实时对局隔离。"""

import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import chess

from chessarena.web import replay
from tests.test_server import ServerFixture


class TestReplayParser(unittest.TestCase):
    def test_mainline_comments_variations_and_multiple_games(self):
        text = '\ufeff[White "模型A"]\n[Black "模型B"]\n\n1. e4 {说明} e5 (1... c5) 2. Nf3 $1 Nc6 *\n\n[Event "Second"]\n\n1. d4 d5 1/2-1/2'
        games = replay.parse_pgn(text)["games"]
        self.assertEqual(len(games), 2)
        first = games[0]
        self.assertEqual(first["headers"]["White"], "模型A")
        self.assertEqual([move["uci"] for move in first["moves"]], ["e2e4", "e7e5", "g1f3", "b8c6"])
        self.assertEqual(len(first["frames"]), 5)
        board = chess.Board()
        for move in first["moves"]:
            board.push_uci(move["uci"])
        self.assertEqual(first["frames"][-1]["fen"], board.fen(en_passant="fen"))
        self.assertEqual(games[1]["result"], "1/2-1/2")
        self.assertEqual(replay.parse_pgn(first["pgn"])["games"][0]["moves"], first["moves"])

    def test_custom_fen_black_first_and_recorded_result(self):
        game = replay.parse_pgn('[SetUp "1"]\n[FEN "7k/8/8/8/8/8/8/K6R b - - 0 17"]\n[Result "1-0"]\n\n17... Kg7 18. Rh7+ 1-0')["games"][0]
        self.assertEqual([(m["side"], m["fullmove_number"]) for m in game["moves"]], [("b", 17), ("w", 18)])
        self.assertEqual(game["result"], "1-0")
        self.assertTrue(game["frames"][-1]["is_check"])

    def test_castling(self):
        game = replay.parse_pgn('1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 4. O-O *')["games"][0]
        board = chess.Board(game["frames"][-1]["fen"])
        self.assertEqual(board.piece_at(chess.G1).symbol(), "K")
        self.assertEqual(board.piece_at(chess.F1).symbol(), "R")

    def test_en_passant_captures_and_raw_ep_square(self):
        game = replay.parse_pgn('1. e4 a6 2. e5 d5 3. exd6 *')["games"][0]
        self.assertEqual(game["frames"][1]["fen"].split()[3], "e3")
        self.assertEqual(game["frames"][-1]["captured"], {"w": [], "b": ["p"]})
        self.assertEqual(game["frames"][0]["captured"], {"w": [], "b": []})
        self.assertIsNone(chess.Board(game["frames"][-1]["fen"]).piece_at(chess.D5))

    def test_promotion(self):
        game = replay.parse_pgn('[FEN "7k/P7/8/8/8/8/8/7K w - - 0 1"]\n\n1. a8=N *')["games"][0]
        self.assertEqual(game["moves"][0]["uci"], "a7a8n")
        self.assertEqual(chess.Board(game["frames"][-1]["fen"]).piece_at(chess.A8).symbol(), "N")

    def test_does_not_stop_at_platform_automatic_draw(self):
        game = replay.parse_pgn('1. Nf3 Nf6 2. Ng1 Ng8 3. Nf3 Nf6 4. Ng1 Ng8 5. e4 *')["games"][0]
        self.assertEqual(len(game["moves"]), 9)
        self.assertEqual(game["moves"][-1]["uci"], "e2e4")

    def test_zero_move_games_are_allowed(self):
        game = replay.parse_pgn('[Event "Not started"]\n\n*')["games"][0]
        self.assertEqual(len(game["frames"]), 1)
        self.assertEqual(game["moves"], [])

    def test_compact_headers_are_not_silently_discarded(self):
        games = replay.parse_pgn('[White "A"][Black "B"] [Result "1-0"] 1. e4 1-0\n\n[Event "Next"][White "C"] *')["games"]
        self.assertEqual(len(games), 2)
        self.assertEqual(games[0]["headers"]["White"], "A")
        self.assertEqual(games[0]["headers"]["Black"], "B")
        self.assertEqual(games[0]["result"], "1-0")
        self.assertEqual(games[1]["headers"]["White"], "C")

    def test_result_integrity(self):
        for text in ('[Result "0-1"]\n\n1. e4 e5 1-0', '1. e4 1-0 e5 *', '1. e4 * 0-1'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                replay.parse_pgn(text)
        game = replay.parse_pgn('[Result "*"]\n\n1. e4 1-0')["games"][0]
        self.assertEqual(game["result"], "1-0")

    def test_duplicate_headers_cannot_overwrite_recorded_metadata(self):
        for text in ('[Result "1-0"] [Result "0-1"] 1. e4 0-1',
                     '[White "A"]\n[White "B"]\n\n*',
                     '[Result "*"] [Result "*"] *'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                replay.parse_pgn(text)

    def test_rejects_damaged_illegal_or_nonstandard_record(self):
        for text in (None, 123, "", "nonsense", "1. e4 e5 2. Bogus *", "1. e5 *", "1. e4 {missing",
                     "1. e4 ) *", "1. -- *", '[FEN "8/8/8/8/8/8/8/8 w - - 0 1"]\n\n*',
                     '[Variant "Atomic"]\n\n1. e4 *', '[Result "bad"]\n\n*'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                replay.parse_pgn(text)

    def test_limits(self):
        for text in (" " * (replay.MAX_BYTES + 1), '[Event "' + "a" * replay.MAX_BYTES + '"]\n\n*',
                     ("[Event \"Empty\"]\n\n*\n\n" * (replay.MAX_GAMES + 1))):
            with self.assertRaises(ValueError):
                replay.parse_pgn(text)

    def test_move_limit_counts_variations(self):
        text = '1. e4 e5 (1... c5) 2. Nf3 Nc6 *'
        with patch.object(replay, "MAX_MOVES", 4), self.assertRaises(ValueError):
            replay.parse_pgn(text)
        with patch.object(replay, "MAX_MOVES", 5):
            self.assertEqual(len(replay.parse_pgn(text)["games"][0]["moves"]), 4)


class TestRecordStore(unittest.TestCase):
    def setUp(self):
        Path("runs").mkdir(exist_ok=True)

    def test_only_pgn_inside_allowed_roots(self):
        with tempfile.TemporaryDirectory(dir="runs") as directory:
            root = Path(directory)
            (root / "runs/nested").mkdir(parents=True)
            (root / "runs/nested/game.PGN").write_text("1. e4 *", encoding="utf-8-sig")
            (root / "secret.pgn").write_text("1. d4 *", encoding="utf-8")
            (root / "runs/ignored.txt").write_text("private", encoding="utf-8")
            store = replay.RecordStore({"runs": root / "runs", "results": root / "results"})
            self.assertEqual([r["id"] for r in store.list()["records"]], ["runs/nested/game.PGN"])
            self.assertEqual(store.read("runs/nested/game.PGN"), "1. e4 *")
            for record_id in ("runs/../secret.pgn", "other/secret.pgn", "runs/ignored.txt", "runs/absent.pgn",
                              "runs/..\\secret.pgn", "runs//secret.pgn", "", None):
                with self.subTest(record_id=record_id), self.assertRaises(ValueError):
                    store.read(record_id)
            self.assertFalse((root / "results").exists())

    def test_oversize_and_non_utf8(self):
        with tempfile.TemporaryDirectory(dir="runs") as directory:
            path = Path(directory) / "game.pgn"
            store = replay.RecordStore({"runs": directory})
            for data in (b"x" * (replay.MAX_BYTES + 1), b"\xff\xfe"):
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    store.read("runs/game.pgn")

    def test_symlink_cannot_escape_root(self):
        with tempfile.TemporaryDirectory(dir="runs") as directory:
            root = Path(directory)
            (root / "runs").mkdir()
            (root / "secret.pgn").write_text("*", encoding="utf-8")
            try:
                (root / "runs/link.pgn").symlink_to(root / "secret.pgn")
            except OSError:
                self.skipTest("当前Windows账户没有创建符号链接权限")
            store = replay.RecordStore({"runs": root / "runs"})
            self.assertEqual(store.list()["records"], [])
            with self.assertRaises(ValueError):
                store.read("runs/link.pgn")


class TestReplayHttp(unittest.TestCase):
    def test_replay_endpoints_do_not_mutate_live_game(self):
        with ServerFixture("api", "api") as fx:
            fx.post("/move", {"move": "d2d4", "side": "w"})
            before = fx.get("/state")[1]
            status, data = fx.post("/replay/parse", {"pgn": "1. e4 e5 *"})
            self.assertEqual(status, 200)
            self.assertEqual(len(data["games"][0]["frames"]), 3)
            for payload in ({}, {"pgn": "1. e5 *"}, {"pgn": "garbage"}, {"pgn": [1]},
                            {"pgn": '[Result "0-1"]\n\n1. e4 1-0'}, {"pgn": '1. e4 * e5'}):
                self.assertEqual(fx.post("/replay/parse", payload)[0], 400)
            Path("runs").mkdir(exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="replay-test-", dir="runs") as directory:
                path = Path(directory) / "game.pgn"
                path.write_text('1. Nf3 *', encoding="utf-8")
                record_id = path.relative_to(Path.cwd()).as_posix()
                self.assertIn(record_id, [record["id"] for record in fx.get("/replay/records")[1]["records"]])
                self.assertEqual(fx.get("/replay/records/" + record_id)[1]["games"][0]["moves"][0]["san"], "Nf3")
            after = fx.get("/state")[1]
            for field in ("fen", "history", "game_id", "revision", "over"):
                self.assertEqual(before[field], after[field], field)
            self.assertEqual(fx.post("/move", {"move": "d7d5", "side": "b"})[0], 200)
