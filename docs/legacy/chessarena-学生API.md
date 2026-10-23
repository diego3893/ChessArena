# ChessArena学生API

本文对应学生接口v2：平台提供只读局面，学生自行编码、推理、判合法和解码，动作经裁判执行。

## 1 接入方式

学生提交`agents/A.py`、`agents/B.py`等入口；平台扫描`agents/`第一层Python文件。网络定义、编码器、解码器可放在各自子目录，权重位置由入口脚本决定。

```bash
python -m chessarena serve --white agents/A.py --black agents/B.py
python -m chessarena test agents/A.py --vs agents/B.py --games 10
```

网页白黑方下拉框也可选择这两个模型。基础平台不需要PyTorch；神经网络选手安装`pip install -r requirements-pytorch.txt`。

## 2 State：只读局面

`choose_move(state)`、`self.game.state`和`Client.state()`提供同一种数据对象，包含：

| 成员 | 含义 |
|---|---|
| `board` | 8×8不可变元组；第0行是第8横线，列0为a列；大写白子，小写黑子，`.`为空 |
| `fen` | 完整FEN，保留原始吃过路兵目标格 |
| `turn` | 当前走子方，`w`或`b` |
| `castling_rights` | `KQkq`的子集或`-` |
| `ep_square` | 吃过路兵目标格，如`e3`，没有则为None |
| `halfmove_clock` / `fullmove_number` | 半回合计数和完整回合编号 |
| `start_fen` / `history` / `ply` | 起始局面、已发生的UCI着法元组和半步数 |
| `game_id` | 当前对局标识 |
| `is_check` / `is_game_over` | 当前将军标记和裁判终局标记 |
| `result` / `over_reason` | 结果及终局原因；未结束时为None |
| `last_error` | 上次拒绝的原因；成功落子后清空 |
| `pretty()` / `copy()` | 字符棋盘；不可变对象的copy返回自身 |

**State不提供`legal_moves`、`apply()`、动作掩码或规则引擎对象。**`Board`仅有`fen/turn/is_check/is_game_over/result`及`get(x, y)/piece_at(sq)/is_empty(x, y)/matrix()/ascii()`读取方法，没有`moves_from()`。

训练时也遵守这一约定。学生可根据FEN和历史维护自己的规则实现；是否允许使用python-chess等库由课程要求决定。仓库中的参考学生示例自行导入python-chess，未从平台领取候选动作。

## 3 Agent与submit

```python
from chessarena import Agent

class MyAgent(Agent):
    name = "我的模型"

    def choose_move(self, state):
        encoded = self.encode(state)       # 学生实现
        output = self.network(encoded)    # 学生实现
        move = self.decode(output, state) # 学生自行判合法并输出UCI
        return self.game.submit(move)
```

编码器、网络和解码器由学生实现；上例展示接口约定，不包含具体训练算法。

`self.game`是绑定执棋颜色的`Player`接口，不是裁判对象。它提供只读`state/board/turn/over/result/history/ply/last_error/game_id`，以及`submit(move, strict=False)`、`resign()`、`clock()`、`wait_my_turn(timeout=10)`。它没有reset、undo、step或修改棋盘的方法。

`Agent`还会收到`color/seed`；可选钩子为`on_game_start(state, color)`、`on_opponent_move(move)`、`on_game_end(result)`、`close()`。模型准备应放在开局钩子中。

也支持直接返回UCI字符串，由平台替你调用裁判。主动submit成功后，平台不会再下一遍；返回失败的Result时，平台用更新后的last_error重新调用choose_move。不要在choose_move里无限自行重试，否则会耗尽同一步时间。

## 4 Result和裁判

着法为小写UCI，例如`e2e4`、`e7e8q`。Result具有`ok/code/reason/move`，支持布尔判断和与整数比较。

| 返回码 | 含义 | HTTP |
|---|---|---|
| `0` | 成功 | 200 |
| `-1` | 非法着法 | 400 |
| `-2` | 格式错误 | 400 |
| `-3` | 越轮、暂停或过期思考 | 409 |
| `-4` | 对局结束 | 410 |

非法动作不改变棋子、轮次或历史，但会更新last_error和拒绝记录。裁判只报告拒绝原因，不列出其他合法动作。strict=True时失败转为异常。

平台驱动的学生Agent默认每步总预算3秒，最多重试3次（初次加重试共4次），共享同一步预算；用尽后按配置判负。已超时的思考线程无法在后续回合通过原请求补交动作。独立HTTP主动提交模式不执行统一思考计时，正式计时评测使用Agent/UCI/平台主动请求的HTTP服务接入。

## 5 PyTorch统一适配

```python
from chessarena.torch_agent import TorchAgent

class MyModel(TorchAgent):
    name = "学生模型"
    device = "cpu"

    def load_model(self):
        # 自己重建网络、加载权重，返回torch.nn.Module
        ...

    def encode(self, state):
        # 自己编码并放到self.device
        ...

    def decode(self, output, state):
        # 自己判合法并解码，返回e2e4等UCI字符串
        ...
```

以上是待学生补全的提交模板。平台不规定通道数、动作编号、网络结构或权重格式，不自动屏蔽、修复或替换非法模型输出。多输入模型可覆盖`predict(encoded)`，例如调用`self._model(**encoded)`。

TorchAgent在开局时调用load_model，执行to(device)、eval和预热；推理使用inference_mode。扫描下拉框时不加载权重。choose_move会把decode结果交给Player.submit；独立推理可调用decide(state)，然后自行调用Client.submit。

可直接运行的完整参考见[模型提交说明](chessarena-模型提交规范.md)。网络加载方式参见[PyTorch官方文档](https://docs.pytorch.org/tutorials/beginner/basics/saveloadrun_tutorial.html)。

## 6 训练与比赛

```python
from chessarena import Arena
from agents.A import ModelA
from agents.B import ModelB

arena = Arena(live=False)
try:
    game = arena.new_game(white=ModelA(), black=ModelB())
    game.run_to_end(max_plies=600)
    print(game.result)
finally:
    arena.close()
```

训练脚本可用Arena创建/重置对局、通过Game.state读取数据、用Game.player("w")取得受限接口。Game是训练管理者/裁判使用的对象，不注入学生模型；学生训练与比赛得到的State相同，也不提供动作列表或平台沙盘。

## 7 独立进程Client

```bash
python -m chessarena serve --white api --black builtin:stockfish
python agents/examples/http_client_agent.py --side w
```

Client(url, side="w")提供state()/board()/submit(move)/wait_my_turn(timeout=10)/pgn()/close()；reset()是本机训练管理功能。GET /state只返回局面；POST /move提交`{"move":"e2e4","side":"w"}`。旧GET /legal_moves已删除，所有HTTP和WebSocket快照均无legal_moves字段。

本机管理接口不构成账号权限隔离；同进程Python插件也是可信代码接口，不是针对反射和任意导入的安全沙箱。

## 8 工具与其他接入

`uci(x1, y1, x2, y2, promo="")`、`square(x, y)`、`xy("e2")`仅做坐标/字符串转换，不判断规则。

UCI引擎和HTTP服务可通过agents/agents.json注册。平台请求HTTP学生服务时只发送State数据，服务自行判合法并返回`{"move":"e2e4"}`。详见[API总表](chessarena-API总表.md)。
