"""样例三：用 ``Client`` 把 AI 跑在另一个进程/机器上（跨进程接入）。

先起服务：``python -m chessarena serve --white human --black builtin:greedy``，
再另开一个终端：``python agents/examples/http_client_agent.py``。

它演示的是"方法名同构"：``c.submit("e2e4")`` 和同进程的 ``game.submit("e2e4")``
返回同样的 ``Result``；``c.state()`` 返回同样的 ``State``。
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chessarena import Client  # noqa: E402（先把项目根放进 sys.path）


def main():
    client = Client("http://127.0.0.1:8000", side="b")  # 假设你是黑方
    while True:
        state = client.state()
        if state.is_game_over:
            print("结束：", state.result)
            return
        if state.turn != "b":
            time.sleep(0.3)
            continue
        move = state.legal_moves[0]  # 换成你的搜索
        result = client.submit(move)
        if not result.ok:
            print("被拒：", result.reason)


if __name__ == "__main__":
    main()
