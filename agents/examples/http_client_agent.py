"""样例三：用 ``Client`` 把 AI 跑在另一个进程/机器上（跨进程接入）。

先起服务：``python -m chessarena serve --white api --black builtin:stockfish``，
再另开一个终端：``python agents/examples/http_client_agent.py``。

它演示的是"方法名同构"：``c.submit("e2e4")`` 和同进程的 ``game.submit("e2e4")``
返回同样的 ``Result``；``c.state()`` 返回同样的 ``State``。
"""

import argparse
import sys
import time
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chessarena import Client  # noqa: E402（先把项目根放进 sys.path）


def main():
    parser = argparse.ArgumentParser(description="通过平台API主动下棋的最小示例")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--side", choices=("w", "b"), default="w")
    args = parser.parse_args()
    client = Client(args.url, side=args.side)
    while True:
        state = client.state()
        if state.is_game_over:
            print("结束：", state.result)
            return
        if state.turn != args.side:
            time.sleep(0.3)
            continue
        # 学生自行判断合法性；可替换为自己的编码器、模型和解码器。
        move = sorted(m.uci() for m in chess.Board(state.fen).legal_moves)[0]
        result = client.submit(move)
        if not result.ok:
            print("被拒：", result.reason)
            time.sleep(0.3)


if __name__ == "__main__":
    main()
