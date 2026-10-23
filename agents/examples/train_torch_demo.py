"""短训两个独立网络，演示学生自行编码、训练、保存并接入平台。

此脚本只是接入演示，不代表训练出了有竞争力的棋手。
"""

import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--out", type=Path, default=ROOT / "agents" / "weights")
    parser.add_argument("--force", action="store_true", help="覆盖已有演示权重")
    args = parser.parse_args()
    if args.steps < 1:
        parser.error("steps须至少为1")
    paths = [args.out / (name+".pt") for name in ("A", "B")]
    if not args.force and any(path.exists() for path in paths):
        parser.error("已有权重；请指定新out目录，或用--force重新训练演示权重")

    import chess
    import torch
    from agents.examples._torch_student import (
        STUDENT_ENCODING, action_index, build_network, encode_position,
    )
    from chessarena import State

    torch.set_num_threads(1)
    rng = random.Random(42)
    board = chess.Board()
    states, targets = [], []
    for _ in range(32):
        if board.is_game_over():
            board.reset()
        # 学生自己的规则库和数据采样。标签为随机合法动作，仅验证训练闭环。
        move = rng.choice(sorted(move.uci() for move in board.legal_moves))
        states.append(encode_position(State(board)))
        targets.append(action_index(move))
        board.push_uci(move)
    inputs = torch.cat(states)
    labels = torch.tensor(targets, dtype=torch.long)
    args.out.mkdir(parents=True, exist_ok=True)
    for seed, (path, hidden) in enumerate(zip(paths, (24, 40))):
        torch.manual_seed(seed)
        model = build_network(hidden)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.003)
        model.train()
        for _ in range(args.steps):
            optimizer.zero_grad()
            loss = torch.nn.functional.cross_entropy(model(inputs), labels)
            loss.backward()
            optimizer.step()
        torch.save({"encoding": STUDENT_ENCODING, "hidden": hidden,
                    "state_dict": model.state_dict(), "demo_only": True}, path)
        print("%s: hidden=%d, steps=%d, loss=%.4f" % (path, hidden, args.steps, loss.item()))
    print("示例短训完成；用于接入验证，不代表棋力。")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
