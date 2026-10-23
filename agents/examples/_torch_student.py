"""学生拥有的完整示例：网络、编码、解码和规则筛选均在agents/内。

这里使用的12通道和20480动作仅是本示例约定，平台不要求其他学生采用。
本示例用学生自己导入的python-chess生成合法着法，可替换为自己的规则实现。
"""

from pathlib import Path

import chess

from chessarena.torch_agent import TorchAgent

PIECES = "PNBRQKpnbrqk"
PROMOTIONS = " qrbn"
STUDENT_ENCODING = "example-pieces12-uci20480-v1"


def encode_position(state, device="cpu"):
    import torch

    # 固定白方视角，第0行是第8横线；此示例把其他元信息留给解码器。
    planes = [[[float(cell == symbol) for cell in row] for row in state.board]
              for symbol in PIECES]
    return torch.tensor(planes, dtype=torch.float32, device=device).unsqueeze(0)


def action_index(move):
    promotion = PROMOTIONS.index(move[4]) if len(move) == 5 else 0
    return (chess.parse_square(move[:2])*64+chess.parse_square(move[2:4]))*5+promotion


def decode_output(output, state):
    # 学生自行判合法。state上没有legal_moves、apply或平台动作掩码。
    moves = sorted(move.uci() for move in chess.Board(state.fen).legal_moves)
    if not moves:
        return None
    scores = output[0]
    indices = [action_index(move) for move in moves]
    selected = int(scores[indices].argmax().item())
    return moves[selected]


def build_network(hidden):
    from torch import nn

    return nn.Sequential(nn.Flatten(), nn.Linear(12*8*8, hidden), nn.ReLU(),
                         nn.Linear(hidden, 64*64*5))


class ExampleStudent(TorchAgent):
    weights = None

    def load_model(self):
        import torch

        path = Path(self.weights)
        if not path.is_file():
            raise FileNotFoundError("缺少%s；先运行python agents/examples/train_torch_demo.py" % path)
        saved = torch.load(path, map_location="cpu", weights_only=True)
        if saved.get("encoding") != STUDENT_ENCODING:
            raise ValueError("权重与本学生示例的编码版本不一致")
        model = build_network(int(saved["hidden"]))
        model.load_state_dict(saved["state_dict"], strict=True)
        return model

    def encode(self, state):
        return encode_position(state, self.device)

    def decode(self, output, state):
        return decode_output(output, state)
