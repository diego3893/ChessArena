# API调用规范

本文对应当前学生接口v2。所有动作都必须由裁判接受后生效；学生读取的是只读局面数据，不会得到平台生成的候选动作或动作掩码。模型相关示例见[PyTorch模型训练与接入示例](PyTorch模型训练与接入示例.md)。

## 1 接口边界

```text
只读State → 学生编码器 → 学生网络 → 学生解码器/合法性判断
                                           ↓ UCI字符串
                           Player.submit / Client.submit
                                           ↓
                                     棋盘裁判Game
                                           ↓ 接受
                                     修改真实局面
```

`Game`是平台或训练环境的管理对象；注入学生`Agent.game`的实际对象是绑定颜色的`Player`，不提供`reset()`、`undo()`、`step()`或真实棋盘。管理程序可以调用Game重开、悔棋和导出，但学生不得把这些能力作为选手接口。

学生可以自行导入规则库，例如`chess.Board(state.fen)`。这是学生自己的本地计算，不是调用平台动作接口；修改该本地棋盘不会影响裁判。

## 2 只读局面State

### 2.1 字段

| Python字段 | 类型 | 含义 |
|---|---|---|
| `fen` | `str` | 完整六段FEN，含走子方、易位权、EP目标及计数 |
| `board` | `tuple[tuple[str, ...], ...]` | 8×8棋子矩阵，第0行对应第8横线 |
| `turn` | `str` | `w`白方、`b`黑方 |
| `castling_rights` | `str` | 如`KQkq`，无易位权为`-` |
| `ep_square` | `str或None` | 原始吃过路兵目标格，如`e3` |
| `halfmove_clock` | `int` | 自最近兵移动或吃子后的半步数 |
| `fullmove_number` | `int` | FEN回合数，从1开始，黑走后增加 |
| `history` | `tuple[str, ...]` | 从`start_fen`开始的成功UCI动作历史 |
| `ply` | `int` | `len(history)`，不是`fullmove_number` |
| `start_fen` | `str` | 此对局或重置后的起点 |
| `game_id` | `str或None` | 平台对局标识；手工构造State时可能为空 |
| `last_error` | `str或None` | 最近拒绝原因；成功提交后清空 |
| `is_check` | `bool` | 当前走子方是否受将 |
| `is_game_over` | `bool` | 平台是否已经终局，含超时/认输等 |
| `result` | `str或None` | `1-0`、`0-1`、`1/2-1/2`；进行中为`None` |
| `over_reason` | `str或None` | 终局原因，见[规则文档](平台象棋规则.md) |

棋子编码：白方`PNBRQK`，黑方`pnbrqk`，空格为`.`。矩阵`board[0][0]`是`a8`，`board[7][0]`是`a1`。不是每次轮到黑方就自动翻转；学生如需当前走子方视角，要在自己的编码器中转换。

`ep_square`存在不代表一定有合法吃过路兵动作。例如`e2e4`后会保留`e3`，即使黑方没有可执行该吃子的兵。请结合完整规则判断。

### 2.2 方法与快照

- `state.pretty()`：返回棋盘及FEN文本。
- `state.copy()`：不可变对象，直接返回自身。
- `state.to_json()`：转为JSON兼容字典。
- `State.from_json(data)`：从平台快照重建数据对象。

JSON中`board/history`变为数组，`is_game_over`对应字段名为`over`。State没有`legal_moves`、`apply()`或底层规则棋盘。旧State是旧快照；提交后若需要新局面，请重新读取`self.game.state`或`client.state()`。

重复局面的判定需要历史；只从当前FEN新建本地棋盘无法还原重复次数。需要复现时，从`start_fen`逐个应用`history`，详见规则文档。

## 3 着法与返回结果

### 3.1 提交格式

只接受小写UCI字符串：

| 操作 | 示例 |
|---|---|
| 普通移动或吃子 | `e2e4`、`g1f3` |
| 王翼、后翼易位 | 白方`e1g1`、`e1c1`；黑方`e8g8`、`e8c8` |
| 升变 | `a7a8q`；后缀只能是`q/r/b/n` |
| 吃过路兵 | 仍写来源格与目标格，如`e5d6` |

不接受SAN、`O-O`、大写格名、空格分隔、连字符或`0000`。必须自己显式决定升变子，不会自动升后。

坐标工具可选：`square(4, 1) == "e2"`、`xy("e2") == (4, 1)`、`uci(4, 1, 4, 3) == "e2e4"`。工具坐标`y=0`从第1横线向上，与矩阵行索引方向相反。

### 3.2 Result

`submit()`正常返回不可变`Result`：`code`、`reason`、`move`和属性`ok`。成功时`move`为接受的UCI，失败时通常为`None`。

| code | 名称 | 含义 | HTTP状态 |
|---|---|---|---|
| 0 | `RC.OK` | 接受 | 200 |
| -1 | `RC.ILLEGAL_MOVE` | 格式可解析，但动作非法 | 400 |
| -2 | `RC.BAD_FORMAT` | 格式错误；也用于无效side/FEN等输入 | 400 |
| -3 | `RC.NOT_YOUR_TURN` | 轮次不符、暂停、旧思考请求等 | 409 |
| -4 | `RC.GAME_OVER` | 对局已结束 | 410 |

```python
result = player.submit("e2e4")
if result.ok:             # 或if result:
    print(result.move)
elif result == -1:        # 也可比较result.code
    print(result.reason)
```

成功Result的布尔值是`True`，而成功数字码是0；不要把`if result.code:`当作成功判断。失败不移动棋子、不切换轮次、不增加成功历史，但可能更新`last_error`、拒绝记录并发出事件。

**已知输入边界：**当前`e2e2`这类同起终点字符串会通过初步格式检查，随后由python-chess抛出`InvalidMoveError`，未统一转成Result。在自动Agent中会按程序异常处置；直接HTTP提交可能返回500。学生应在解码器中排除该输入。网络故障等也可能直接抛异常，不能假定所有失败都有Result。

## 4 同进程Agent与Player

### 4.1 最小选手

保存为`agents/my_agent.py`：

```python
import chess
from chessarena import Agent


class MyAgent(Agent):
    name = "我的选手"

    def choose_move(self, state):
        # 学生自行使用规则库；平台没有给出动作列表。
        moves = sorted(m.uci() for m in chess.Board(state.fen).legal_moves)
        if not moves:
            return None
        return self.game.submit(moves[0])
```

平台也接受`choose_move()`直接返回UCI，由驱动器代为调用裁判。若已主动`submit()`，必须返回该次Result或及时返回，不能再提交另一动作；平台会识别已成功落子，避免重复执行。同一个`choose_move()`内不要另开提交线程。

返回`None`表示弃权，不表示“再等一会”。在非终局下抛普通异常会判负。默认请保留`fast_local=False`与`is_human=False`，让学生选手走带预算的普通路径。

### 4.2 生命周期

| 成员 | 调用时机与约定 |
|---|---|
| `name` | 界面显示名 |
| `self.game` | 开局注入Player，构造时为`None` |
| `self.color` | 开局注入`w/b` |
| `self.seed` | 平台注入整数种子；学生自行设置随机库的种子 |
| `on_game_start(state, color)` | 开局初始化，适合加载模型 |
| `choose_move(state)` | 本方回合获取一个新快照并决策 |
| `on_opponent_move(move)` | 对方成功提交后通知UCI字符串 |
| `on_game_end(result)` | 终局回调，参数为结果字符串 |
| `close()` | 平台释放资源；不应依赖其只调用一次 |

`on_game_start()`不在每步计时中，但没有独立启动时限。`reset()`不重新调用该钩子；新建对局会重新装配。应从每次传入的State同步局面，不要只依赖增量回调维护自己的棋盘。

### 4.3 Player可用成员

| 成员 | 含义 |
|---|---|
| `state` | 读取当前冻结快照，属性，不加括号 |
| `board` | 只读实时棋子视图，属性 |
| `color`、`turn` | 绑定颜色、当前走子方 |
| `over`、`result` | 当前平台终局状态与结果 |
| `history`、`ply`、`last_error`、`game_id` | 对应局面字段 |
| `submit(move, *, strict=False)` | 以绑定颜色提交动作 |
| `resign()` | 绑定方认输 |
| `clock()` | 本方当前一步剩余预算；不在本方回合/已结束时为0 |
| `wait_my_turn(*, timeout=10.0)` | 等待轮到本方；终局或等待超时返回False |

`strict=True`仅同进程接口提供：`-1/-2`转为`IllegalMoveError`，`-3`转为`NotYourTurnError`，`-4`转为`GameOverError`。普通学生Agent中抛出这些异常仍会进入程序异常处置，若需重试应使用普通Result模式。

Board提供`fen/turn/is_check/is_game_over/result`，以及`get(x, y)`、`piece_at("e2")`、`is_empty(x, y)`、`matrix()`、`ascii()`。空格返回`.`；`matrix()`返回可修改的副本，改副本不影响裁判。Board不提供落子或规则生成方法。

### 4.4 在训练环境手动驱动

以下程序由训练器持有Game，网络只接收State和Player：

```python
from chessarena import Arena

arena = Arena(live=False)
try:
    game = arena.new_game(white=None, black="builtin:random")
    player = game.player("w")
    state = player.state
    result = player.submit("e2e4")
    assert result.ok
    game.step()  # 训练器驱动黑方；不是学生Player的方法
    next_state = player.state
    print(state.ply, next_state.ply)  # 0、2
finally:
    arena.close()
```

手动调用Player提交不经过`Game._play_turn()`，因此不自动累计比赛重试次数或触发思考超时。训练器若需要相同计时，应把模型作为Agent交给`game.step()`驱动。`Arena(live=True)`本身不会自动启动网页；网页由`serve`与Session提供。

## 5 学生主动HTTP接入

### 5.1 开放选手位置

```powershell
python -m chessarena serve --white api --black builtin:greedy
```

学生客户端明确使用`side="w"`。需要两个外部模型主动提交时，白黑都设为`api`，分别启动绑定`w/b`的客户端。

```python
import chess
from chessarena import Client

client = Client("http://127.0.0.1:8000", side="w")
try:
    while True:
        state = client.state()
        if state.is_game_over:
            break
        if not client.wait_my_turn(timeout=10.0):
            continue
        state = client.state()
        if state.is_game_over or state.turn != "w":
            continue
        moves = sorted(m.uci() for m in chess.Board(state.fen).legal_moves)
        if not moves:
            break
        result = client.submit(moves[0])
        if not result.ok:
            print(result.code, result.reason)
finally:
    client.close()
```

`Client.state()`和`Client.board()`是方法，分别返回冻结快照和快照棋盘；与Player的属性形式不同。`Client.wait_my_turn(timeout=...)`轮询HTTP，False可能仅表示等待超时，需再检查终局。`Client(timeout=10.0)`的timeout是单次网络请求超时，不是比赛思考时限。

### 5.2 核心端点

| 方法与路径 | 输入 | 输出 |
|---|---|---|
| `GET /state` | 无 | 完整当前会话快照 |
| `POST /move` | `{"move":"e2e4","side":"w"}` | `{"result":{...},"state":{...}}` |
| `GET /pgn` | 无 | PGN纯文本；Python用`client.pgn()` |
| `GET /players` | 无 | 可选内置/学生选手，供界面装配 |
| `GET /debug` | 无 | 驱动存活、停滞计数、最近异常等诊断数据 |

`api`回合必须指定side，side须为`w/b`且与走子方相同；未指定返回`-3`，其他字符串返回`-2`。正常自动AI回合拒绝外部`POST /move`，即使传入正确side。人类回合可以不传side；暂停时拒绝提交。

`POST /move`示例响应如下，`state`此处仅节选：

```json
{
  "result": {"ok": true, "code": 0, "reason": "落子成功：e2e4", "move": "e2e4"},
  "state": {"turn": "b", "ply": 1, "over": false, "result": null}
}
```

实际响应中的state是完整快照；后台AI可能已应手，不能只用`result.move`自行推算当前棋盘。HTTP400/409/410也应解析JSON错误结果；`Client.submit()`已处理这些HTTP错误并返回Result。验证JSON结构、程序崩溃等其他错误不保证使用同一业务封装。

**没有`GET /legal_moves`接口，访问为404。**也没有平台`Client.legal_moves()`或`State.apply()`。

### 5.3 会话快照补充字段

除State序列化字段外，服务端还提供：

| 字段 | 含义 |
|---|---|
| `history_san` | 成功动作的SAN显示历史 |
| `captured` | `w/b`键分别记录该颜色被吃掉的棋子符号 |
| `last_move` | 最近成功UCI或null |
| `white/black` | 选手显示名 |
| `players` | `w/b`对应的选手spec |
| `human/api` | 两种手动选手类型的布尔标记 |
| `paused/speed/timeout` | 会话暂停、展示速度及配置步时 |
| `revision` | 会话状态修订号，用于处理显示快照顺序 |

`revision`不是提交令牌；`POST /move`目前不接收或校验`game_id/revision/expected_ply`。重开后旧客户端仍可能向新局提交，客户端应自行检查对局标识；需要严格防止跨局竞态时应由比赛调度进一步隔离。

## 6 管理接口与推送

### 6.1 管理接口

这些接口用于教师或界面，不应作为模型决策输入或比赛操作：

| 接口 | 行为 |
|---|---|
| `POST /reset`，`{"fen":...}`或`{}` | 清空历史并重置；返回result/state封装；对应`Client.reset(fen=None)` |
| `POST /control`，`{"action":"pause"}` | 暂停 |
| action为`resume/step/undo/resign` | 继续、驱动一步、悔棋、认输 |
| `{"action":"speed","speed":2.0}` | 设置展示速度，最小0.05 |
| `{"action":"new","white":"agents/A.py","black":"agents/B.py"}` | 装配新选手和新对局 |

`/control`成功返回`{"type":"control","paused":...,"speed":...,"state":...}`，不是Result封装；未知动作或开局失败返回HTTP400及`{"error":...}`。`/reset`保留原game_id，`new`通常产生新game_id，因此跟踪重置还需看revision和起始状态。

接口目前没有身份认证；颜色绑定是协议约定，不是访问权限凭据。调用API不能直接替换棋盘矩阵，但管理接口可要求裁判重置；本机插件也不是防篡改沙箱。

### 6.2 WebSocket

连接`ws://127.0.0.1:8000/ws`：

| type | 主要字段 |
|---|---|
| `hello` | `version/state`，连接后立即发送 |
| `move` | `move/ply/state` |
| `illegal` | `move/code/reason`，不带完整state |
| `retry` | `side/attempt/code/reason` |
| `game_over` | `result/reason/state` |
| `reset` | `state` |
| `control` | `paused/speed/state` |
| `heartbeat` | `state`，默认约3秒一次 |
| `pong` | 对客户端`{"type":"ping"}`的响应 |

WebSocket仅用于推送与ping，不接受下棋命令；落子仍走HTTP。若处理丢包、重连、乱序，优先以最新完整state校准，不只依靠增量move。

## 7 平台调用学生HTTP服务与UCI

这与第5节的主动`api`客户端是两种方向。

在`agents/agents.json`加入条目，例如：

```json
[
  {"name":"my_service","type":"http","url":"http://127.0.0.1:9001/choose","timeout":1.5},
  {"name":"my_engine","type":"uci","cmd":["python","agents/my_uci.py"],"timeout":1.5,"options":{}}
]
```

此处`my_uci.py`只是待学生实现的程序路径示例，不是仓库已有文件。注册表顶层为数组，name必须唯一；HTTP必需url，UCI必需cmd。

使用`http:my_service`时，每步平台POST一份`State.to_json()`到学生url，学生返回`{"move":"e2e4"}`。请求不含合法动作。由平台把该move提交裁判，学生服务不应再对同一回合主动调用`/move`。无字符串move会被视为弃权。HTTP失败、网络错误或非法JSON等可转成`TransientError`并计入重试；总步时仍由裁判控制。

使用`uci:my_engine`时，学生实现标准UCI握手与bestmove。当前适配器按当前FEN构造本地棋盘交给引擎，不保证向该引擎传递平台的完整重复历史；若网络需要全历史，优先选择Agent、HTTP服务或主动Client。

## 8 代码依据

[State](../chessarena/core/state.py)、[Board](../chessarena/core/board.py)、[Player](../chessarena/core/player.py)、[Agent](../chessarena/core/agent.py)、[裁判Game](../chessarena/core/game.py)、[Client](../chessarena/client.py)、[HTTP与WS路由](../chessarena/web/server.py)、[会话策略](../chessarena/web/session.py)、[外部选手适配](../chessarena/core/external.py)。
