"""命令行入口：``python -m chessarena <命令>``。

``play`` 跑一局、``serve`` 起网页、``test`` 自测学生 AI、``league`` 跑联赛、
``replay`` 终端回放 PGN。
"""

import argparse
import sys
import time
from pathlib import Path

from . import __version__
from .core.arena import Arena
from .core.game import REASON_TEXT


def _utf8_stdout():
    """让中文输出不依赖控制台代码页（Windows 默认 gbk 会乱码）。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _fmt_seconds(value):
    return "%.2fs" % (value,)


def cmd_play(args):
    arena = Arena(live=False, seed=args.seed, config=args.config)
    game = arena.new_game(
        white=args.white,
        black=args.black,
        fen=args.fen,
        timeout=args.timeout,
        max_retries=args.max_retries,
    )

    if args.verbose:
        def on_move(move, result):
            print("%3d. %-6s %-6s" % (game.ply, move, result.reason), flush=True)

        game.on("move", on_move)

    started = time.monotonic()
    result = game.run_to_end(max_plies=args.max_plies)
    elapsed = time.monotonic() - started

    if not game.over:
        print("!! 达到 max_plies=%d 仍未终局，按未完成处理" % (args.max_plies,))
    reason = REASON_TEXT.get(game.over_reason or "", game.over_reason or "未结束")
    print("结果：%s（%s） · %d 半步 · %s" % (result or "*", reason, game.ply, _fmt_seconds(elapsed)))
    if game.rejected:
        print("被拒 %d 次（非法率 %.1f%%）" % (
            len(game.rejected),
            100.0 * len(game.rejected) / max(1, game.ply + len(game.rejected)),
        ))

    pgn = game.pgn()
    if args.pgn:
        path = Path(args.pgn)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(pgn, encoding="utf-8")
        print("PGN 已写入 %s" % (path,))
    if not args.quiet:
        print()
        print(pgn)
    arena.close()
    return 0 if game.over else 3


def cmd_serve(args):
    from .core.arena import Arena
    from .web.server import serve
    from .web.session import Session

    arena = Arena(live=True, seed=args.seed, config=args.config,
                  timeout=args.timeout, max_retries=args.max_retries)
    server_cfg = arena.config.get("server", {})
    host = args.host or server_cfg.get("host", "127.0.0.1")
    port = args.port or int(server_cfg.get("port", 8000))
    try:
        session = Session(arena, args.white, args.black, fen=args.fen, speed=args.speed)
    except Exception as exc:
        arena.close()
        print("启动失败：%s" % (exc,), file=sys.stderr)
        return 1
    print("ChessArena %s · 页面 http://%s:%d/ · 对手：白=%s 黑=%s"
          % (__version__, host, port, args.white, args.black))
    print("按 Ctrl+C 结束。")
    try:
        serve(session, host=host, port=port)
    except KeyboardInterrupt:
        pass
    finally:
        session.stop()
        arena.close()
    return 0


def cmd_league(args):
    from .league import League

    players = _parse_players(args.players)
    out = args.out or "results/league-%s" % time.strftime("%Y%m%d-%H%M%S")
    league = League(
        players,
        rounds=args.rounds,
        openings=args.openings,
        max_concurrent=args.concurrent,
        seed=args.seed,
        timeout=args.timeout,
        max_plies=args.max_plies,
        config=args.config,
    )
    print("联赛：%d 名选手 · 每对 %d 局（黑白各一）· 随机开局 %d 步 · 并发 %d"
          % (len(players), 2 * args.rounds, args.openings, args.concurrent))
    print("选手：%s" % ("、".join(players),))
    result = league.run(out, progress=print, resume=not args.no_resume)
    print()
    print("%-24s %6s %5s %4s %4s %4s %8s" % ("AI", "ELO", "场次", "胜", "和", "负", "得分率"))
    for row in result.rows:
        print("%-24s %6.0f %5d %4d %4d %4d %7.1f%%  非法率 %.2f%%  平均 %.3fs/步  未完成 %d"
              % (row["name"], row["elo"], row["games"], row["wins"], row["draws"],
                 row["losses"], row["win_rate"], row["illegal_rate"], row["avg_move_seconds"], row["unfinished"]))
    print()
    print("报告：%s" % (result.report_path,))
    print("PGN ：%s" % (result.pgn_dir,))
    return 3 if any(row["unfinished"] for row in result.rows) else 0


def _parse_players(text):
    players = []
    for item in (text or "").split(","):
        item = item.strip()
        if not item:
            continue
        if item.startswith(("builtin:", "agents/", "uci:", "http:")):
            players.append(item)
        else:
            players.append("builtin:" + item)
    return players or ["builtin:random", "builtin:greedy", "builtin:minimax2"]


def _run_for_test(agent, opponent, *, seed, timeout, max_plies, swap, config="config.yaml"):
    """跑一局并记录每步耗时。返回 (result, 我执的颜色, 步时列表)。"""
    arena = Arena(live=False, seed=seed, timeout=timeout, config=config)
    white, black = (opponent, agent) if swap else (agent, opponent)
    try:
        game = arena.new_game(white=white, black=black)
        mine = "b" if swap else "w"
        move_times = []
        while not game.over and game.ply < max_plies:
            side = game.turn
            turn_started = time.monotonic()
            outcome = game.step()
            move_times.append((side, time.monotonic()-turn_started))
            if outcome.code == -3:
                break
        return game.result or "*", mine, move_times, game.ply

    finally:
        arena.close()


def cmd_test(args):
    spec = args.agent
    opponent = args.opponent
    games = max(1, args.games)
    wins = draws = losses = unfinished = 0
    times = []
    rejected = 0
    plies = 0
    started = time.monotonic()

    for i in range(games):
        result, mine, move_times, game_plies = _run_for_test(
            spec, opponent, seed=args.seed + i, timeout=args.timeout,
            max_plies=args.max_plies, swap=(i % 2 == 1), config=args.config,
        )
        mine_times = [seconds for side, seconds in move_times if side == mine]
        times.extend(mine_times)
        plies += game_plies
        if result == "*":
            unfinished += 1
        elif result == "1/2-1/2":
            draws += 1
        elif (result == "1-0" and mine == "w") or (result == "0-1" and mine == "b"):
            wins += 1
        else:
            losses += 1

    total = max(1, wins + draws + losses)
    avg = sum(times) / len(times) if times else 0.0
    longest = max(times) if times else 0.0
    print("%d 胜 %d 和 %d 负 · 胜率 %.1f%% · 平均每步 %.2fs · 最长 %.2fs · 总用时 %.1fs"
          % (wins, draws, losses, 100.0 * wins / total, avg, longest,
             time.monotonic() - started))
    print("对被测方：%s vs %s（%d 局，%d 半步）" % (spec, opponent, games, plies))
    if unfinished:
        print("未完成 %d 局，不计入胜和负" % unfinished)
    return 3 if unfinished else 0


def cmd_replay(args):
    import chess
    import chess.pgn

    path = Path(args.pgn)
    if not path.exists():
        print("找不到 PGN：%s" % (path,), file=sys.stderr)
        return 2
    with path.open("r", encoding="utf-8") as handle:
        game = chess.pgn.read_game(handle)
    if game is None:
        print("这个文件不是 PGN：%s" % (path,), file=sys.stderr)
        return 2

    board = chess.Board()
    if game.headers.get("FEN"):
        board.set_fen(game.headers["FEN"])
    print("白：%s   黑：%s" % (game.headers.get("White", "?"), game.headers.get("Black", "?")))
    line = []
    count = 0
    for count, move in enumerate(game.mainline_moves(), 1):
        san = board.san(move)
        board.push(move)
        line.append(san)
        if len(line) == 2:
            print("%3d. %-7s %-7s" % (count // 2, line[0], line[1]))
            line = []
        if args.board:
            print(board)
        if args.delay:
            time.sleep(args.delay)
    if line:
        print("%3d. %-7s" % (count // 2 + 1, line[0]))
    print("结果：%s" % (game.headers.get("Result", "*"),))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="chessarena",
        description="ChessArena：单机国际象棋 AI 对战场",
    )
    parser.add_argument("--version", action="store_true", help="打印版本后退出")
    sub = parser.add_subparsers(dest="command")

    play = sub.add_parser("play", help="命令行跑一局并打印 PGN")
    play.add_argument("--white", default="builtin:random", help="白方（见 API总表 §10）")
    play.add_argument("--black", default="builtin:greedy", help="黑方")
    play.add_argument("--fen", default=None, help="自定义起始局面")
    play.add_argument("--timeout", type=float, default=None, help="每步总时长（秒）")
    play.add_argument("--max-retries", type=int, default=None, dest="max_retries")
    play.add_argument("--max-plies", type=int, default=400, dest="max_plies")
    play.add_argument("--pgn", default=None, help="把 PGN 写到这个路径")
    play.add_argument("--seed", type=int, default=0)
    play.add_argument("--config", default="config.yaml")
    play.add_argument("--verbose", action="store_true", help="逐步打印")
    play.add_argument("--quiet", action="store_true", help="不打印 PGN 正文")
    play.set_defaults(func=cmd_play)

    serve = sub.add_parser("serve", help="起网页/HTTP 服务")
    serve.add_argument("--white", default="human", help="白方（默认人类）")
    serve.add_argument("--black", default="builtin:greedy", help="黑方")
    serve.add_argument("--fen", default=None)
    serve.add_argument("--host", default=None, help="默认取 config.yaml 的 server.host")
    serve.add_argument("--port", type=int, default=None, help="默认取 config.yaml 的 server.port")
    serve.add_argument("--speed", type=float, default=1.0, help="AI 落子速度倍率")
    serve.add_argument("--timeout", type=float, default=None, help="每步总时长（秒）")
    serve.add_argument("--max-retries", type=int, default=None, dest="max_retries")
    serve.add_argument("--seed", type=int, default=0)
    serve.add_argument("--config", default="config.yaml")
    serve.set_defaults(func=cmd_serve)

    league = sub.add_parser("league", help="跑循环赛并生成 ELO 报告")
    league.add_argument("--players", default="random,greedy,minimax2",
                        help="逗号分隔；可写 random 或 builtin:random 或 agents/x.py")
    league.add_argument("--rounds", type=int, default=2, help="每对下 2*rounds 局（黑白各一）")
    league.add_argument("--openings", type=int, default=8, help="随机开局步数")
    league.add_argument("--concurrent", type=int, default=4, help="并发进程数")
    league.add_argument("--out", default=None, help="输出目录（默认 results/league-<时间>）")
    league.add_argument("--seed", type=int, default=0)
    league.add_argument("--timeout", type=float, default=3.0)
    league.add_argument("--max-plies", type=int, default=600, dest="max_plies")
    league.add_argument("--no-resume", action="store_true", dest="no_resume",
                        help="忽略输出目录里已完成的局")
    league.add_argument("--config", default="config.yaml")
    league.set_defaults(func=cmd_league)

    test = sub.add_parser("test", help="批量自测一个学生 AI")
    test.add_argument("agent", help="如 agents/my_agent.py")
    test.add_argument("--vs", default="builtin:greedy", dest="opponent", help="对手写法")
    test.add_argument("--games", type=int, default=10)
    test.add_argument("--seed", type=int, default=0)
    test.add_argument("--timeout", type=float, default=3.0)
    test.add_argument("--max-plies", type=int, default=400, dest="max_plies")
    test.add_argument("--config", default="config.yaml")
    test.set_defaults(func=cmd_test)

    replay = sub.add_parser("replay", help="终端回放 PGN")
    replay.add_argument("pgn", help="PGN 文件路径")
    replay.add_argument("--delay", type=float, default=0.0, help="每步停顿秒数")
    replay.add_argument("--board", action="store_true", help="每步打印棋盘")
    replay.set_defaults(func=cmd_replay)
    return parser


def main(argv=None):
    _utf8_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "version", False):
        from . import __version__

        print("chessarena %s" % (__version__,))
        return 0
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
