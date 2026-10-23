"""自评脚本：跟两个基线各打 N 盘，给出得分、非法率与耗时。

    python assignments/grade.py agents/my_agent.py --games 12

输出一份 `runs/grade-<名字>.json`，方便对比同学之间/不同版本之间的进步。
"""

import argparse
import json
import sys
import time
from pathlib import Path

# 允许 `python assignments/grade.py ...` 直接跑（把项目根放进 sys.path）
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chessarena import Arena  # noqa: E402（必须在 sys.path 调整之后）
from chessarena.core.game import REASON_TEXT  # noqa: E402

BASELINES = ("builtin:greedy", "builtin:minimax2")


def play_one(spec, opponent, *, swap, seed, timeout, max_plies):
    arena = Arena(live=False, seed=seed, timeout=timeout, config="config.yaml")
    try:
        white, black = (opponent, spec) if swap else (spec, opponent)
        game = arena.new_game(white=white, black=black)
        started = time.monotonic()
        game.run_to_end(max_plies=max_plies)
        elapsed = time.monotonic() - started
        mine = "b" if swap else "w"
        if game.result == "1/2-1/2":
            score = 0.5
        elif (game.result == "1-0" and mine == "w") or (game.result == "0-1" and mine == "b"):
            score = 1.0
        elif game.result is None:
            score = 0.5  # 未终局按和棋计，避免"拖时间"刷分
        else:
            score = 0.0
        return {
            "opponent": opponent,
            "color": mine,
            "result": game.result or "*",
            "reason": game.over_reason or "unfinished",
            "plies": game.ply,
            "rejected": len(game.rejected),
            "seconds": round(elapsed, 3),
            "score": score,
        }
    finally:
        arena.close()


def main():
    parser = argparse.ArgumentParser(description="ChessArena 作业自评")
    parser.add_argument("agent", help="如 agents/my_agent.py")
    parser.add_argument("--games", type=int, default=10, help="每个基线的局数")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--max-plies", type=int, default=400, dest="max_plies")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    games = []
    started = time.monotonic()
    for opponent in BASELINES:
        for i in range(max(1, args.games)):
            games.append(play_one(
                args.agent, opponent, swap=(i % 2 == 1), seed=args.seed + i,
                timeout=args.timeout, max_plies=args.max_plies,
            ))

    print("%-22s %6s %6s %8s %10s" % ("对手", "场次", "得分", "得分率", "非法率"))
    summary = {}
    for opponent in BASELINES:
        rows = [g for g in games if g["opponent"] == opponent]
        score = sum(g["score"] for g in rows)
        plies = sum(g["plies"] for g in rows)
        rejected = sum(g["rejected"] for g in rows)
        rate = 100.0 * score / max(1, len(rows))
        illegal = 100.0 * rejected / max(1, plies + rejected)
        print("%-22s %6d %6.1f %7.1f%% %9.2f%%" % (opponent, len(rows), score, rate, illegal))
        summary[opponent] = {
            "games": len(rows), "score": score, "score_rate": round(rate, 1),
            "illegal_rate": round(illegal, 2),
            "avg_seconds_per_game": round(sum(g["seconds"] for g in rows) / max(1, len(rows)), 2),
        }

    total_score = sum(g["score"] for g in games)
    total_rate = 100.0 * total_score / max(1, len(games))
    print()
    print("总计：%d 局 · 得分 %.1f · 得分率 %.1f%% · 用时 %.1fs"
          % (len(games), total_score, total_rate, time.monotonic() - started))
    for name in ("timeout", "retry_exhausted", "forfeit", "error"):
        bad = [g for g in games if g["reason"] == name]
        if bad:
            print("  %s：%d 局" % (REASON_TEXT.get(name, name), len(bad)))

    out = Path("runs") / ("grade-%s.json" % (Path(args.agent).stem,))
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        "agent": args.agent, "games": games, "summary": summary,
        "total_score_rate": round(total_rate, 1),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("明细：%s" % (out,))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
