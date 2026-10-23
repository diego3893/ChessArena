"""联赛：循环赛 + ELO + 报告。

一条命令跑完：编排 → 每局独立进程（或顺序）→ 算 ELO → 写 HTML 报告与 PGN。
`max_concurrent=1` 时全部在本进程顺序执行（便于调试与沙箱内测试）。
"""

import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

import chess

from .core.arena import Arena

DEFAULT_MAX_PLIES = 600


# ---------------------------------------------------------------- 单局
def play_game(job: dict) -> dict:
    """跑一局并返回记录。必须是模块级函数，``ProcessPoolExecutor`` 才能 pickle。"""
    arena = Arena(
        live=False,
        seed=job.get("seed", 0),
        timeout=job.get("timeout", 3.0),
        max_retries=job.get("max_retries", 3),
        config=job.get("config", "config.yaml"),
    )
    started = time.monotonic()
    opening: list[str] = []
    try:
        game = arena.new_game(white=job["white"], black=job["black"])
        rng = random.Random(job.get("opening_seed", 0))
        for _ in range(int(job.get("opening_plies", 0))):
            if game.over:
                break
            moves = sorted(m.uci() for m in chess.Board(game.state.fen).legal_moves)
            if not moves:
                break
            move = rng.choice(moves)
            if game.submit(move).ok:
                opening.append(move)
        player_stats = {side: {"plies": 0, "rejected": 0, "seconds": 0.0}
                        for side in ("w", "b")}
        while not game.over and game.ply < job.get("max_plies", DEFAULT_MAX_PLIES):
            side, before = game.turn, game.ply
            turn_started = time.monotonic()
            result = game.step()
            player_stats[side]["seconds"] += time.monotonic()-turn_started
            player_stats[side]["plies"] += game.ply-before
            if result.code == -3:
                break
        for rejection in game.rejected:
            player_stats[rejection["side"]]["rejected"] += 1
        seconds = time.monotonic() - started
        record = {
            "idx": job["idx"],
            "white": job["white"],
            "black": job["black"],
            "result": game.result or "*",
            "reason": game.over_reason or "unfinished",
            "plies": game.ply,
            "rejected": len(game.rejected),
            "seconds": round(seconds, 3),
            "game_id": game.game_id,
            "opening": opening,
            "player_stats": player_stats,
            "pgn": game.pgn(),
        }
        return record
    except Exception as exc:  # 单局出错不该毁掉整个联赛
        return {
            "idx": job["idx"],
            "white": job["white"],
            "black": job["black"],
            "result": "*",
            "reason": "error: %r" % (exc,),
            "plies": 0,
            "rejected": 0,
            "seconds": round(time.monotonic() - started, 3),
            "game_id": "",
            "opening": opening,
            "pgn": "",
        }
    finally:
        arena.close()


# ---------------------------------------------------------------- ELO
def score_of(result: str, color: str) -> float | None:
    """把 ``1-0`` / ``0-1`` / ``1/2-1/2`` 换成某一方的得分。"""
    if result == "1/2-1/2":
        return 0.5
    if result == "1-0":
        return 1.0 if color == "w" else 0.0
    if result == "0-1":
        return 0.0 if color == "w" else 1.0
    return None


def expected_score(rating: float, opponent: float) -> float:
    return 1.0 / (1.0 + 10 ** ((opponent - rating) / 400.0))


def compute_ratings(records, *, start=1500.0, k=32.0):
    """按时间顺序逐局更新（标准 400 分制）。"""
    ratings = {}
    for rec in records:
        for side in (rec["white"], rec["black"]):
            ratings.setdefault(side, start)
        white, black = rec["white"], rec["black"]
        rw, rb = ratings[white], ratings[black]
        score_w = score_of(rec["result"], "w")
        if score_w is None:
            continue
        expected_w = expected_score(rw, rb)
        ratings[white] = rw + k * (score_w - expected_w)
        ratings[black] = rb + k * ((1.0 - score_w) - (1.0 - expected_w))
    return ratings


def summarize(records, ratings):
    """每人一行统计：场次、胜和负、得分率、非法率、平均每步耗时。"""
    table = {}
    for rec in records:
        for side, color in ((rec["white"], "w"), (rec["black"], "b")):
            row = table.setdefault(side, {
                "name": side, "games": 0, "wins": 0, "draws": 0, "losses": 0,
                "score": 0.0, "plies": 0, "rejected": 0, "seconds": 0.0, "unfinished": 0,
            })
            row["games"] += 1
            score = score_of(rec["result"], color)
            if score is None:
                row["unfinished"] += 1
            elif score == 1.0:
                row["wins"] += 1
            elif score == 0.5:
                row["draws"] += 1
            else:
                row["losses"] += 1
            row["score"] += score if score is not None else 0.0
            stats = rec.get("player_stats", {}).get(color, {})
            row["plies"] += stats.get("plies", 0)
            row["rejected"] += stats.get("rejected", 0)
            row["seconds"] += stats.get("seconds", 0.0)
    rows = []
    for name, row in table.items():
        games = max(1, row["games"]-row["unfinished"])
        moves = max(1, row["plies"] + row["rejected"])
        rows.append({
            **row,
            "elo": round(ratings.get(name, 1500.0), 1),
            "win_rate": round(100.0 * row["score"] / games, 1),
            "illegal_rate": round(100.0 * row["rejected"] / moves, 2),
            "avg_move_seconds": round(row["seconds"] / max(1, row["plies"]), 3),
        })
    return sorted(rows, key=lambda r: r["elo"], reverse=True)


# ---------------------------------------------------------------- 联赛
@dataclass
class LeagueResult:
    records: list
    ratings: dict
    rows: list
    report_path: Path
    pgn_dir: Path


class League:
    """单循环（每对下 ``2*rounds`` 局，双方各执黑一次）。"""

    def __init__(self, players, *, rounds=2, openings=8, max_concurrent=4,
                 seed=0, timeout=3.0, max_retries=3, max_plies=DEFAULT_MAX_PLIES,
                 config="config.yaml"):
        if len(players) < 2:
            raise ValueError("联赛至少要两个选手")
        self.players = [str(p) for p in players]
        self.rounds = max(1, int(rounds))
        self.openings = max(0, int(openings))
        self.max_concurrent = max(1, int(max_concurrent))
        self.seed = int(seed)
        self.timeout = float(timeout)
        self.max_retries = int(max_retries)
        self.max_plies = int(max_plies)
        self.config = config

    # ------------------------------------------------------------------
    def schedule(self):
        """生成对局列表：``[(idx, white, black, opening_seed), ...]``。"""
        jobs = []
        idx = 0
        for round_no in range(self.rounds):
            for i in range(len(self.players)):
                for j in range(i + 1, len(self.players)):
                    first, second = self.players[i], self.players[j]
                    for white, black in ((first, second), (second, first)):
                        jobs.append({
                            "idx": idx,
                            "round": round_no + 1,
                            "white": white,
                            "black": black,
                            "opening_seed": self.seed * 1000 + idx,
                            "opening_plies": self.openings,
                            "seed": self.seed,
                            "timeout": self.timeout,
                            "max_retries": self.max_retries,
                            "max_plies": self.max_plies,
                            "config": self.config,
                        })
                        idx += 1
        return jobs

    def run(self, out_dir="results", *, progress=None, resume=True):
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        pgn_dir = out / "pgn"
        pgn_dir.mkdir(exist_ok=True)
        log_path = out / "games.jsonl"

        jobs = self.schedule()
        done = {}
        if resume and log_path.exists():
            for line in log_path.read_text(encoding="utf-8").splitlines():
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict) and "idx" in rec and score_of(rec.get("result"), "w") is not None:
                    done[rec["idx"]] = rec
        if not resume:
            log_path.write_text("", encoding="utf-8")
        pending = [job for job in jobs if job["idx"] not in done]
        if progress:
            progress("共 %d 局，已完成 %d，待跑 %d" % (len(jobs), len(done), len(pending)))

        records = [done[job["idx"]] for job in jobs if job["idx"] in done]
        order = {job["idx"]: job for job in jobs}

        if self.max_concurrent <= 1:
            for job in pending:
                rec = play_game(job)
                records.append(rec)
                self._persist(rec, pgn_dir, log_path)
                if progress:
                    progress(self._line(rec, order))
        else:
            from concurrent.futures import ProcessPoolExecutor

            with ProcessPoolExecutor(max_workers=self.max_concurrent) as pool:
                for rec in pool.map(play_game, pending):
                    records.append(rec)
                    self._persist(rec, pgn_dir, log_path)
                    if progress:
                        progress(self._line(rec, order))

        records.sort(key=lambda r: r["idx"])
        ratings = compute_ratings(records)
        rows = summarize(records, ratings)
        report = out / "index.html"
        report.write_text(self._render_html(rows, records), encoding="utf-8")
        (out / "ratings.json").write_text(
            json.dumps({"ratings": ratings, "rows": rows}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return LeagueResult(records, ratings, rows, report, pgn_dir)

    # ------------------------------------------------------------------
    @staticmethod
    def _line(rec, order):
        job = order.get(rec["idx"], {})
        return "%3d/%s  %-22s vs %-22s  %-7s %-14s %3d 步 %.1fs" % (
            rec["idx"] + 1, job.get("round", "?"), rec["white"], rec["black"],
            rec["result"], rec["reason"], rec["plies"], rec["seconds"],
        )

    @staticmethod
    def _persist(rec, pgn_dir, log_path):
        if rec["pgn"]:
            (pgn_dir / ("%s.pgn" % (rec["game_id"],))).write_text(rec["pgn"], encoding="utf-8")
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({k: v for k, v in rec.items() if k != "pgn"},
                                    ensure_ascii=False) + "\n")

    def _render_html(self, rows, records):
        from string import Template

        # 用 Template 而不是 %-format：模板里有 CSS 的 % 和大括号
        head = Template("""<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>ChessArena 联赛</title>
<style>
body{font:14px/1.6 "Segoe UI","Microsoft YaHei",system-ui,sans-serif;background:#14161a;color:#e6e9ef;margin:0;padding:24px}
h1{font-size:20px;margin:0 0 4px} .sub{color:#8b93a3;margin-bottom:18px}
table{border-collapse:collapse;width:100%;max-width:1000px;margin-bottom:26px}
th,td{padding:7px 10px;border-bottom:1px solid #2f3540;text-align:left;font-variant-numeric:tabular-nums}
th{color:#8b93a3;font-weight:500;font-size:12px}
tr:nth-child(1) td{background:rgba(122,162,247,.08)}
.badge{color:#7aa2f7} .small{color:#8b93a3;font-size:12px}
a{color:#7aa2f7;text-decoration:none} a:hover{text-decoration:underline}
</style><h1>ChessArena 联赛报告</h1>
<div class="sub">seed $seed · $players 名选手 · $games 局 · 生成于 $when</div>
""").substitute(seed=self.seed, players=len(self.players),
                games=len(records), when=time.strftime("%Y-%m-%d %H:%M"))
        table = ["<table><tr><th>#</th><th>AI</th><th>ELO</th><th>场次</th><th>胜</th><th>和</th><th>负</th>"
                 "<th>未完成</th><th>得分率</th><th>非法率</th><th>平均每步</th></tr>"]
        for pos, row in enumerate(rows, 1):
            table.append(
                "<tr><td>%d</td><td>%s</td><td class='badge'>%.0f</td><td>%d</td>"
                "<td>%d</td><td>%d</td><td>%d</td><td>%d</td><td>%.1f%%</td><td>%.2f%%</td><td>%.3fs</td></tr>"
                % (pos, row["name"], row["elo"], row["games"], row["wins"],
                   row["draws"], row["losses"], row["unfinished"], row["win_rate"], row["illegal_rate"],
                   row["avg_move_seconds"])
            )
        table.append("</table>")
        games = ["<table><tr><th>#</th><th>白</th><th>黑</th><th>结果</th><th>原因</th>"
                 "<th>步数</th><th>用时</th><th>PGN</th></tr>"]
        for rec in records:
            link = ""
            if rec.get("game_id"):
                link = "<a href='pgn/%s.pgn'>下载</a>" % (rec["game_id"],)
            games.append(
                "<tr><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td class='small'>%s</td>"
                "<td>%d</td><td>%.1fs</td><td>%s</td></tr>"
                % (rec["idx"] + 1, rec["white"], rec["black"], rec["result"],
                   rec["reason"], rec["plies"], rec["seconds"], link)
            )
        games.append("</table>")
        return head + "\n".join(table) + "\n" + "\n".join(games) + "\n</html>\n"
