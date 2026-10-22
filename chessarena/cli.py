"""命令行入口：``python -m chessarena <命令>``。

阶段 1 只实现 ``play``（命令行跑一局并打印 PGN）与 ``version``；
``serve`` / ``league`` / ``test`` / ``replay`` 会在后续阶段接上。
"""

import argparse
import sys
import time
from pathlib import Path

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


def cmd_stub(args):
    print("命令 %r 尚未实现（阶段 1 只有 play / version）。见 PROJECT_CONTEXT.md §6。" % (args.command,))
    return 2


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

    for name in ("serve", "league", "test", "replay"):
        stub = sub.add_parser(name, help="（尚未实现）")
        stub.set_defaults(func=cmd_stub)
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
