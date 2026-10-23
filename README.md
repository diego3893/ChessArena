# ChessArena

面向研讨课的国际象棋AI对战平台，供学生训练、接入和评测自己的选手。支持网页人机对战、模型之间的对战，以及命令行批量比赛。

平台使用chessground展示棋盘，使用python-chess执行裁判，通过UCI接入Stockfish。学生可以编写搜索算法，也可以接入自己训练的PyTorch网络。

## 设计约定

学生自行实现**编码器、网络、合法性判断和解码器**。平台提供完整的只读局面数据，不提供候选动作、动作掩码或局面推演接口。

```text
读取局面 → 学生编码器 → 网络推理 → 学生解码器 → submit() → 裁判检查 → 落子
```

所有选手共用同一裁判。学生拿到的`State`是不可变快照，`Player`是绑定执子颜色的提交接口；修改学生侧数据不会改变真实棋盘。着法统一使用小写UCI字符串，例如`e2e4`、`a7a8q`。

## 启动平台

需要Python3.10或以上。以下命令均在仓库根目录、同一个Python环境中执行：

```powershell
python -m pip install -r requirements.txt
python -m chessarena serve
```

浏览器访问<http://127.0.0.1:8000/>，默认人类执白、贪心AI执黑。通过页面顶部下拉框选择双方选手；更改选手会开新局。

基础平台无需安装PyTorch、GPU或前端构建工具。Windows也可使用`start.bat`启动；虚拟环境安装步骤见[平台使用说明](docs/平台使用说明.md)。

与Stockfish对战：

```powershell
python -m chessarena serve --white human --black builtin:stockfish
```

仓库附带Stockfish19的Windows x86-64可执行文件。其他系统需要在`config.yaml`的`stockfish.path`中指定兼容引擎。可用内置选手为`random`、`greedy`、`minimax2`、`minimax3`和`stockfish`，均使用`builtin:名称`选择。

## 接入学生选手

### Python选手

将入口放在`agents/`第一层，例如`agents/my_agent.py`：

```python
import chess
from chessarena import Agent


class MyAgent(Agent):
    name = "我的选手"

    def choose_move(self, state):
        # 合法动作由学生自己的规则库生成。
        moves = sorted(m.uci() for m in chess.Board(state.fen).legal_moves)
        if not moves:
            return None
        return self.game.submit(moves[0])
```

刷新页面后即可选择该选手。`self.game`是`Player`接口，提交的动作仍须经过裁判。也可以直接返回UCI字符串，由平台提交。

### PyTorch模型

运行仓库中的A/B模型示例：

```powershell
python -m pip install -r requirements-pytorch.txt
python agents/examples/train_torch_demo.py --steps 20
python -m chessarena serve --white agents/A.py --black agents/B.py
```

训练脚本生成两份独立权重，默认不覆盖已有文件。A/B只是使用随机合法动作标签的短训示例，用于验证训练和接入流程，不代表棋力。权重未纳入Git，克隆后需要生成。

自己的模型可继承`TorchAgent`，实现`load_model()`、`encode(state)`与`decode(output, state)`。平台负责开局加载、推理模式和裁判提交，不要求双方网络具有相同输入输出形状。

完整流程见[PyTorch模型训练与接入示例](docs/PyTorch模型训练与接入示例.md)，交付要求见[模型提交规范](docs/模型提交规范.md)。

### 独立程序通过API接入

先为外部程序开放白方位置：

```powershell
python -m chessarena serve --white api --black builtin:stockfish
```

在另一个终端运行示例客户端：

```powershell
python agents/examples/http_client_agent.py --side w
```

| 接口 | 用途 |
|---|---|
| `GET /state` | 读取完整当前局面 |
| `POST /move` | 提交`{"move":"e2e4","side":"w"}` |
| `GET /pgn` | 导出棋谱 |
| `WS /ws` | 订阅局面与对局事件 |

Python可使用`Client(url, side="w")`调用相同接口，其他语言可直接使用HTTP。平台也支持主动请求学生HTTP推理服务或UCI引擎，具体协议见[API调用规范](docs/API调用规范.md)。

## 自动比赛与评测

生成示例权重后，可以脱离网页运行模型对战、自测或循环赛：

```powershell
# 一局比赛，保存棋谱
python -m chessarena play --white agents/A.py --black agents/B.py --pgn runs/A-vs-B.pgn

# 交换执子颜色自测
python -m chessarena test agents/A.py --vs builtin:greedy --games 2

# 循环赛，每对选手黑白各一局
python -m chessarena league --players agents/A.py,agents/B.py --rounds 1 --openings 0 --concurrent 1 --out results/A-vs-B
```

联赛输出HTML报告、比赛记录、ELO估计和PGN。断点续跑须使用相同的`--out`目录及比赛设置；更换模型后应使用新目录。

网页顶部可切换“实时对战／播放器”。在终端保存PGN后，进入播放器选择本地文件，或直接从`runs/`、`results/`的记录列表载入。支持多盘PGN、播放/暂停、逐步、进度定位、点击着法跳转和倍速；回放只读，实时对局继续运行。完整流程见[播放器使用说明](docs/平台使用说明.md#32-播放器)。

比赛配置位于`config.yaml`。自动AI默认每步3秒，首次失败后可再重试3次，全部尝试共享时间预算。主动HTTP的`api`模式目前不强制相同的步时与重试判负。

棋子走法采用普通国际象棋规则；平台会自动判三次重复和50步和棋。半步上限、未完成比赛及部分联赛统计也有特定处理，正式评分前应阅读[平台象棋规则](docs/平台象棋规则.md)。

## 文档

| 文档 | 内容 |
|---|---|
| [平台使用说明](docs/平台使用说明.md) | 环境安装、页面操作、启动参数、配置与排错 |
| [API调用规范](docs/API调用规范.md) | 只读状态、选手接口、返回码、HTTP与WebSocket |
| [PyTorch模型训练与接入示例](docs/PyTorch模型训练与接入示例.md) | 编码、训练样本、网络输出、解码、权重加载与比赛 |
| [模型提交规范](docs/模型提交规范.md) | 入口目录、模型文件、环境说明与提交验收 |
| [平台象棋规则](docs/平台象棋规则.md) | 实际裁判规则、平台差异与当前限制 |

`docs/legacy/`保留历史设计资料，当前使用以以上文档和代码为准。

## 仓库结构

```text
chessarena/       裁判、选手接口、内置AI、引擎适配、网页服务与CLI
agents/           学生选手入口、模型权重与参考示例
assignments/      搜索与评估作业骨架
docs/             使用文档和接口规范
tests/            单元、集成与文档契约测试
vendor/           chessground前端资源
thirdparty/       Stockfish、第三方许可证与对应源码归档
config.yaml       运行配置
```

修改平台后运行现有测试：

```powershell
python -m unittest discover -s tests -t .
# 可选：本地已安装Node时，验证播放器时钟与定位逻辑；运行平台无需Node
node --test tests/replay.test.mjs
```

## 许可证

ChessArena采用[GPL-3.0-or-later](LICENSE)。第三方组件保留各自版权与许可，归属见[第三方声明](THIRD_PARTY_NOTICES.md)，附带组件的版本、源码和校验值见[第三方分发说明](thirdparty/README.md)。
