# PyTorch模型训练与接入示例

本文展示数据怎样经过学生编码器进入网络，网络输出怎样由学生解码器转换成UCI，再交给平台`submit()`。示例只演示可运行流程，不规定训练算法，也不代表有竞争力的棋力。

**平台统一的是State、Player和选手生命周期，不统一网络结构、输入通道、动作编号或合法性算法。**本文的12通道和20480输出只属于学生示例，A/B可以使用完全不同的结构。先阅读[API调用规范](API调用规范.md)。

## 1 跑通仓库已有示例

在仓库根目录、同一个Python环境中执行：

```powershell
python -m pip install -r requirements-pytorch.txt
python agents/examples/train_torch_demo.py --steps 20
python -m chessarena play --white agents/A.py --black agents/B.py --pgn runs/torch-demo.pgn
python -m chessarena serve --white agents/A.py --black agents/B.py
```

有已有权重时，训练脚本会拒绝覆盖；确需重新生成演示权重时使用`--force`。输出路径默认是`agents/weights/A.pt`、`B.pt`。这两个文件被Git忽略，新克隆不会自带。

| 文件 | 作用 |
|---|---|
| [`_torch_student.py`](../agents/examples/_torch_student.py) | 学生侧编码、动作编号、解码、网络与权重读取 |
| [`train_torch_demo.py`](../agents/examples/train_torch_demo.py) | 采集32条演示样本，短训并保存A/B权重 |
| [`A.py`](../agents/A.py)、[`B.py`](../agents/B.py) | 两个可被平台发现的独立选手入口 |
| [`torch_agent.py`](../chessarena/torch_agent.py) | 平台可选生命周期适配器，不包含统一编码器 |

A模型隐藏层为24，B模型为40，各自训练各自加载，说明对战双方无需相同参数量。下文沿用这些学生侧函数，避免训练和比赛维护两套不同的编码约定。

## 2 学生编码器：从State到张量

仓库示例编码器的等价实现如下：

```python
import torch

PIECES = "PNBRQKpnbrqk"


def encode_position(state, device="cpu"):
    planes = [
        [[float(cell == piece) for cell in row] for row in state.board]
        for piece in PIECES
    ]
    return torch.tensor(
        planes, dtype=torch.float32, device=device
    ).unsqueeze(0)
```

输入是只读State；输出形状为`[1, 12, 8, 8]`：

- 第一个维度是batch；一个局面为1。
- 12个通道按白兵、白马、白象、白车、白后、白王、黑方对应六种棋子排列。
- 该位置存在该类棋子为1，否则为0；空格所有棋子通道均为0。
- 固定白方视角：第0行第0列是`a8`，不因执黑而自动翻转。

这个演示编码**省略了走子方、易位权、EP目标、计数与历史**，所以不能完整表达所有不同棋局状态。解码器仍使用完整FEN检查合法性，但这不能补回网络未看到的信息。正式模型应自行决定怎样编码`turn`、`castling_rights`、`ep_square`、计数和重复历史，并在训练与推理中保持一致。

平台不会强迫学生使用上述通道，也不会自动给tensor转设备。自定义编码器应把输入放到`self.device`；可以返回tensor，也可以返回字典、元组等自定义输入。

## 3 学生动作编号与解码器

### 3.1 示例动作编号

示例选择“来源64格×目标64格×升变5种”作为分类输出，即20480维。升变槽顺序为无升变、后、车、象、马；格号按`a1=0`到`h8=63`。

```python
import chess

PROMOTIONS = " qrbn"


def action_index(move):
    from_id = chess.parse_square(move[:2])
    to_id = chess.parse_square(move[2:4])
    promotion = PROMOTIONS.index(move[4]) if len(move) == 5 else 0
    return (from_id * 64 + to_id) * 5 + promotion
```

这里的格号不是二维矩阵的行优先编号。不要将`state.board[row][col]`的row直接当成棋盘rank；矩阵row与rank相反。

这个编号空间包含大量非法组合，例如来源等于目标、轮次不符、受将、错误升变等。编号存在不代表动作合法。

### 3.2 从网络输出到UCI

```python
import chess


def decode_output(output, state):
    # 学生自行导入规则库、重建局面、生成合法候选。
    moves = sorted(move.uci() for move in chess.Board(state.fen).legal_moves)
    if not moves:
        return None
    scores = output[0]  # [20480]，这里预期batch=1
    indices = [action_index(move) for move in moves]
    chosen = int(scores[indices].argmax().item())
    return moves[chosen]
```

该解码器只在学生自己算出的合法动作上选择最高分。它没有读取平台合法动作接口；换成学生自己写的规则生成器也可以。如果学生选择直接对全部输出argmax再解码，非法结果会由裁判拒绝，平台不会自动纠正或补选。

如果采用完全不同的动作表示，也可以输出来源/目标两个分布、序列token、策略和值两个分支等；只需由学生最终解码为一个UCI字符串。无论解码器如何保证合法性，最终仍须通过裁判。

## 4 把样本交给网络训练

### 4.1 样本是什么

最简单的监督样本是`(局面State, 目标UCI)`：

```text
State → encode_position → [1, 12, 8, 8]
目标UCI → action_index → 一个整数标签

拼接N个局面 → [N, 12, 8, 8]
标签列表    → [N]，dtype=torch.long
网络输出    → [N, 20480]
```

目标动作可以来自学生数据集、自己的教师策略或自博弈采样。下面仅用学生自己的规则库随机选择合法动作，验证张量、梯度、保存和比赛接入。随机标签不能当作强棋手训练方法。

### 4.2 一个完整短训程序

保存为仓库根目录的`train_my_model.py`。默认输出`agents/weights/MyModel.pt`，存在时拒绝覆盖：

```python
from pathlib import Path
import random

import chess
import torch
from chessarena import State
from agents.examples._torch_student import (
    STUDENT_ENCODING,
    action_index,
    build_network,
    encode_position,
)


def main():
    torch.set_num_threads(1)
    torch.manual_seed(7)
    rng = random.Random(7)
    states, labels = [], []
    board = chess.Board()  # 学生自己的数据采样棋盘

    for _ in range(32):
        if board.is_game_over():
            board.reset()
        state = State(board)  # 复制为平台同形状的只读数据
        moves = sorted(move.uci() for move in board.legal_moves)
        target = rng.choice(moves)
        states.append(encode_position(state))
        labels.append(action_index(target))
        board.push_uci(target)

    x = torch.cat(states, dim=0)
    y = torch.tensor(labels, dtype=torch.long)
    hidden = 24
    model = build_network(hidden)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.003)
    model.train()

    for _ in range(20):
        optimizer.zero_grad()
        logits = model(x)
        loss = torch.nn.functional.cross_entropy(logits, y)
        loss.backward()
        optimizer.step()

    path = Path(__file__).resolve().parent / "agents" / "weights" / "MyModel.pt"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"不覆盖已有权重：{path}")
    torch.save({
        "encoding": STUDENT_ENCODING,
        "hidden": hidden,
        "state_dict": model.state_dict(),
        "demo_only": True,
    }, path)
    print(f"保存至{path}，loss={loss.item():.4f}")


if __name__ == "__main__":
    main()
```

`build_network(hidden)`是学生目录中这个简单网络：

```python
from torch import nn


def build_network(hidden):
    return nn.Sequential(
        nn.Flatten(),
        nn.Linear(12 * 8 * 8, hidden),
        nn.ReLU(),
        nn.Linear(hidden, 64 * 64 * 5),
    )
```

训练时不能在`torch.inference_mode()`内执行前向与反向；平台TorchAgent的推理流程只用于评估和比赛。真实训练可加入DataLoader、批次迭代、验证集与检查点，但编码、标签含义和权重格式始终由学生负责。

### 4.3 通过平台采集交互数据

如果希望训练过程也使用同一裁判，可以由训练器创建Game，以Player提交动作：

```python
import chess
from chessarena import Arena

arena = Arena(live=False)
samples = []
try:
    game = arena.new_game(white=None, black="builtin:random")
    player = game.player("w")
    while not game.over and game.ply < 20:
        if game.turn == "b":
            game.step()
            continue
        before = player.state
        # 此处可换成学生编码器、网络和解码器。
        move = sorted(m.uci() for m in chess.Board(before.fen).legal_moves)[0]
        result = player.submit(move)
        after = player.state
        samples.append((before, move, result.code, after))
        if not result.ok:
            break  # 演示程序避免死循环；实际训练自行定义失败处理
finally:
    arena.close()
```

训练器自行把样本转成监督标签或奖励；平台不定义reward、优势估计、loss或优化器。`after`是本方动作刚提交后的状态，通常轮到对手；如需要“一次本方决策到下次本方决策”的转移，应再驱动对手后读取新State。达到20半步只停止采集，不自动产生和棋标签。

## 5 把训练权重接入平台

### 5.1 自定义TorchAgent入口

保存为`agents/my_model.py`，与第4.2节生成的权重配套：

```python
from pathlib import Path

from chessarena.torch_agent import TorchAgent
from agents.examples._torch_student import (
    STUDENT_ENCODING,
    build_network,
    decode_output,
    encode_position,
)


class MyModel(TorchAgent):
    name = "我的PyTorch模型"
    device = "cpu"

    def load_model(self):
        import torch

        path = Path(__file__).resolve().parent / "weights" / "MyModel.pt"
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
        if checkpoint["encoding"] != STUDENT_ENCODING:
            raise ValueError("权重的编码版本不匹配")
        model = build_network(int(checkpoint["hidden"]))
        model.load_state_dict(checkpoint["state_dict"], strict=True)
        return model

    def encode(self, state):
        return encode_position(state, device=self.device)

    def decode(self, output, state):
        return decode_output(output, state)
```

这里复用`agents/examples/`中的学生代码以展示闭环。真实提交应包含自己的模型定义、编码器和解码器，不能只提供一个不明结构的`.pt`。

```powershell
python train_my_model.py
python -m chessarena test agents/my_model.py --vs builtin:random --games 2
python -m chessarena serve --white agents/my_model.py --black builtin:greedy
python -m chessarena play --white agents/my_model.py --black agents/B.py --pgn runs/MyModel-vs-B.pgn
```

最后一条命令需要先生成B的演示权重。入口类需要能无参数实例化；扫描`agents/`时会导入文件并创建实例，所以不要在模块导入或构造器中训练、启动服务或读大权重。

### 5.2 适配器实际做了什么

开局时`TorchAgent.on_game_start()`调用`prepare(state)`：延迟导入torch、调用学生`load_model()`、确认返回`torch.nn.Module`、执行`.to(device).eval()`，并默认使用初始State预热一次。

每步调用链：

```text
choose_move(state)
  → decide(state)
    → inference_mode
    → encode(state)
    → predict(encoded)，默认model(encoded)
    → decode(output, state)，由学生返回UCI
  → self.game.submit(UCI)
  → 返回裁判Result给驱动器
```

模型加载与预热发生在逐步计时之前；编码、前向、解码和提交属于本步工作。平台不替学生检查所有输出分数，也不替学生筛选合法动作。`decode()`返回None将被视为弃权。

对于多个输入或字典输入，可覆盖：

```python
def predict(self, encoded):
    return self._model(**encoded)
```

默认`device="cpu"`便于复现；GPU可由学生改为`cuda`并自行保证设备可用。`map_location="cpu"`先读取权重，适配器再移动模型，编码器也必须使用同一设备。CPU路径已在本项目验证，GPU与新环境需自行验证。

`weights_only=True`是本示例采用的读取方式，不是平台规定的checkpoint结构。保存的`encoding/hidden/state_dict`键同样是学生示例约定，其他网络可以有不同格式。

## 6 独立进程中的PyTorch模型主动调用API

先启动平台：

```powershell
python -m chessarena serve --white api --black builtin:greedy
```

保存下面程序为仓库根目录的`run_model_client.py`，在另一终端运行。它复用第5节的学生类，但使用`decide()`，不会要求平台注入`self.game`：

```python
import time
from chessarena import Client
from agents.my_model import MyModel

model = MyModel()
client = Client("http://127.0.0.1:8000", side="w")
try:
    while True:
        state = client.state()
        if state.is_game_over:
            print("终局：", state.result, state.over_reason)
            break
        if state.turn != "w":
            time.sleep(0.1)
            continue
        move = model.decide(state)  # 学生encode → 网络 → decode
        if move is None:
            break  # 仅结束客户端；不会自动向服务端认输
        result = client.submit(move)
        if not result.ok:
            print("提交被拒：", result.code, result.reason)
            time.sleep(0.1)
finally:
    model.close()
    client.close()
```

主动HTTP模式适合调试和交互训练，当前没有正式自动计时/重试判负，也没有跨局提交令牌。需要平台按每步预算驱动两个网络时，优先直接用`agents/A.py`与`agents/B.py`；若要保持推理服务独立运行，使用API规范中平台主动调用的`http:名字`方式。

## 7 交付前检查

训练与比赛必须使用相同通道顺序、视角、归一化、动作编号和升变约定；保存checkpoint时记录相应版本信息。分别验证执白、执黑、受将、易位、吃过路兵与升变。训练集中的最终奖励应以平台`result/over_reason`为准，不能仅从当前FEN猜测是否结束。

交付清单、目录布局和资源说明见[模型提交规范](模型提交规范.md)；裁判差异见[平台象棋规则](平台象棋规则.md)。
