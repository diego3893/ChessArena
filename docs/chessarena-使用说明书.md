# ChessArena 国际象棋 AI 对战场 · 使用说明书

> 版本：v1 设计稿
> 适用：一门研讨课，学生自己写 AI 来下棋
> 一句话：**本地启动一个网页，你点着下棋、或者看两个 AI 互相打；学生写一个 Python 类就能参赛；AI 既能被平台调用，也能自己 `game.submit()` 主动落子；内置 5 档现成 AI 当陪练和基线；一条命令跑完整联赛并算出 ELO。**

---

## 快速开始（3 分钟）

```bash
git clone <本仓库> && cd ChessArena
pip install -r requirements.txt
python -m chessarena serve
```

浏览器打开 **http://127.0.0.1:8000** 就能下棋了。

- Windows 用户：直接双击 `start.bat`，等价于上面两条命令。
- 不需要装 Node、不需要数据库、不需要 GPU。
- 前端棋盘已经打包成静态文件，`pip install` 完就能用。

---

## 一、界面总览

打开就是这样一个页面，**左边棋盘，右边信息，底部控制**：

```
┌──────────────────────────────────────────────────────────────────────────┐
│ ♞ ChessArena        白方 [人类 ▾] vs 黑方 [贪心 (L2) ▾]  [开局]    已连接 │
├──────────────────────────────────────┬───────────────────────────────────┤
│                                      │ ● 贪心 (L2)          黑   AI      │
│     8  ♜ ♞ ♝ ♛ ♚ ♝ ♞ ♜               │ ○ 人类               白   人      │
│     7  ♟ ♟ ♟ ♟ ♟ ♟ ♟ ♟               │ ───────────────────────────────── │
│     6  · · · · · · · ·                │ 着法                              │
│     5  · · · · · · · ·                │  1. d4    f5                      │
│     4  · · · ♙ · · · ·                │  2. f4    g5                      │
│     3  · · · · · · · ·                │                                   │
│     2  ♙ ♙ ♙ ♙ · ♙ ♙ ♙               │ 吃子  白吃 —   黑吃 —             │
│     1  ♖ ♘ ♗ ♕ ♔ ♗ ♘ ♖               │                                   │
│        a b c d e f g h                │                                   │
│   （e2 已选中，e3/e4 高亮为可走点）   │                                   │
├──────────────────────────────────────┴───────────────────────────────────┤
│ [新对局] [悔棋] [认输] [翻转] [导出PGN] [复制FEN]  速度 0.25× 1× 4× 瞬间 │
└──────────────────────────────────────────────────────────────────────────┘
```

**棋盘上你能看到的效果**：

| 交互 | 表现 |
|---|---|
| 点击自己的棋子 | 该子高亮，所有合法落点显示为小圆点（吃子位置显示为空心圈） |
| 拖拽走子 | 松手即落子；走到非法位置会自动弹回 |
| 走完之后 | 上一步的起点和终点标黄，方便复盘 |
| 被将军 | 王所在格子红框闪烁，顶部提示"将军！" |
| 兵到底线 | 弹出 4 个升变选项（后/车/象/马）让你点 |
| 对局结束 | 棋盘变灰不可点，中间浮出"白方胜 · 将杀"，同时列出终局原因（将杀 / 逼和 / 三次重复 / 50 步 / 认输 / 超时） |
| 悔棋 | 一步退两步（连 AI 的应手一起退），随时可用 |

**右侧面板**：双方名称与执子方标记（人 / AI）、SAN 记谱列表、被吃棋子。局面上方显示"谁走棋 · 第几步 · 每步限时"。

> v1 只有**每步限时**（默认 3.0s，含重试），没有整盘倒计时；界面上显示的是限时提示而不是 10:00 倒计时。

**底部按钮**：新对局 / 悔棋 / 认输 / 翻转棋盘（执黑时用）/ 导出 PGN / 复制 FEN。

---

## 二、玩法（先选双方模型）

### 0. 先选双方模型（所有玩法的入口）

页面顶部有两个下拉框：**白方** 与 **黑方**，各自可选：

- `人类` —— 你（或同学）点击/拖拽走子；
- `随机 (L1)` / `贪心 (L2)` / `Minimax 深度2 (L3)` / `Minimax 深度3 αβ (L4)` / `Stockfish (L5)`；
- 之后 `agents/` 里学生的 AI 也会出现在这里。

改任一下拉框，或点「开局」，就会按当前选择**重开一局**。三种组合对应三种玩法：

| 白方 | 黑方 | 玩法 |
|---|---|---|
| 人类 | 任一 AI | 人机对战 |
| 任一 AI | 任一 AI | 机机对战（可观战、可暂停/单步/调速） |
| 人类 | 人类 | 同机双人（自带裁判，不会走错） |

### 1. 人机对战
白方选「人类」，黑方选一个档位。**内置 5 档，难度是刻意拉开的**：

| 档位 | 名字 | 实现 | 大致棋力 |
|---|---|---|---|
| L1 | 随机 | 从合法着法里随便挑 | 完全不会下，用来验证接口通了 |
| L2 | 贪心 | 每步吃价值最高的子，否则随机 | 会白吃子，但常自己送子 |
| L3 | minimax 深度 2 | 纯 minimax + 子力评估 | 像刚学棋的人 |
| L4 | minimax 深度 3 + alpha-beta | 同样评估函数，加了剪枝 | 能看出两步杀，班级中位数 |
| L5 | Stockfish | 限制到 1320–3190 分（`UCI_Elo`，默认 1600；每步 0.6s） | 认真下打不过 |

> **这 5 档不是黑盒**：L1–L4 每一档都是 `builtin/` 目录下一个 50–150 行的独立文件。
> 这就是给学生的第一份教材——"L4 比 L3 只多了 alpha-beta 十几行，但快 5 倍"。

### 2. 机机对战（观战）
白方、黑方各选一个 AI（可以相同，也可以 L1 vs L5 看吊打）。两个 AI 自动轮流走子，**你会看到棋子自己动起来**。

- 速度可调：`0.25× / 1× / 4× / 瞬间`（瞬间 = 20×，每步几乎不停顿）
- 随时可「暂停 / 继续 / 单步」
- 一方出错会弹出原因（如"黑方重试次数用尽，判负"），不会静默卡住

### 3. 学生 AI vs 内置 AI
下拉框里会**自动出现** `agents/` 目录下你写的所有 `Agent`（以及 `agents/agents.json` 里注册的 UCI / HTTP 对手），选它就能下场，跟内置档位对打。

### 4. 联赛（最实用的教学工具）
一条命令跑循环赛，生成一份 HTML 排行榜：

```bash
python -m chessarena league --players random,greedy,minimax2,agents/张同学.py \
    --rounds 2 --openings 8 --concurrent 4
```

- 每对选手下 `2*rounds` 局，黑白各一次；开局先随机走 `openings` 步，避免所有对局一模一样。
- 报告在 `results/league-<时间>/index.html`，包含：ELO 榜、胜/和/负、得分率、**非法率**、平均每步耗时，以及每局 PGN 下载链接。
- 进度实时打印在终端；中途中断后**重跑同一条命令会跳过已完成的局**（结果记录在 `results/league-*/games.jsonl`）。

### 5. 复盘
每局都能存 PGN：页面「导出 PGN」，或 `python -m chessarena play --pgn runs/x.pgn`。
终端回放：

```bash
python -m chessarena replay runs/x.pgn            # 快速过一遍记谱
python -m chessarena replay runs/x.pgn --board --delay 0.3   # 每步打印棋盘
```

页面内的逐帧回放（读 `runs/<game_id>.jsonl` 录像）留作后续版本。

---

## 三、学生怎么接入自己的 AI（核心章节）

三种方式，按需要选，**都进同一个下拉框**。

### 方式一：Python 类（推荐，90% 的学生用这个）

在 `agents/` 目录新建 `my_agent.py`：

```python
from chessarena import Agent, State

class MyAgent(Agent):
    name = "张同学·迭代加深"          # 会显示在界面上

    def choose_move(self, state: State) -> str:
        # 返回 UCI 格式着法，如 "e2e4"、"g1f3"、"e7e8q"（升变要带子）
        move = self.search(state, depth=3)
        return move
```

保存后**刷新页面就出现在下拉框里**，不用重启服务（开发模式自动热加载）。

### 方式二：UCI 引擎（任何语言）

如果你用 C++/Rust/Java 写，只要你的程序能说 UCI，在 `agents/agents.json` 里加一条：

```json
[
  {
    "name": "我的C++Bot",
    "type": "uci",
    "cmd": ["./my_bot", "--threads", "1"],
    "timeout": 5.0,
    "options": {"Threads": 1}
  }
]
```

平台会自己拉起进程、发 `uci` / `isready` / `position fen ...` / `go movetime`，读回 `bestmove`。你已经写好的 Stockfish 风格引擎可以零改动接入。完整字段与线协议见《API总表》§15。

### 方式三：HTTP 服务（远程 / 要用 GPU）

```json
[
  { "name": "云端神经网络", "type": "http", "url": "http://10.0.0.5:9000/move", "timeout": 10 }
]
```

平台 POST 一个 JSON 过去：

```json
{ "fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
  "turn": "w", "ply": 2, "history": ["e2e4", "e7e5"],
  "legal_moves": ["d2d4", "g1f3", "..."] }
```

你回 `{"move": "g1f3"}` 就行（回 `null` 视为弃权判负）。适合把模型放在实验室服务器上跑。字段细节见《API总表》§15.3。

### 学生自测命令（强烈推荐写进作业要求）

```bash
# 跟内置 L2 打 20 盘，看胜率——提交前自己先验证
python -m chessarena test agents/my_agent.py --vs builtin:greedy --games 20

# 跟你同学的 AI 打 10 盘
python -m chessarena test agents/my.py --vs agents/li.py --games 10
```

输出：`10 胜 2 和 8 负 · 胜率 50% · 平均每步 0.42s · 最长 1.8s`。
**"平均每步用时"这一栏会让学生自己意识到复杂度问题**，比讲一百遍大 O 有用。

---

## 四、给 AI 用的 API 手册

### `State`：你能看到的世界（只读）

```python
state.fen          # str  当前局面，标准 FEN
state.turn         # str  "w" / "b"（白 / 黑）
state.board        # 8×8 只读矩阵，'P'白兵 'p'黑兵 'N'白马 ... '.' 空
                   #      行序：board[0] 是第 8 行（黑方底线）
state.legal_moves  # tuple[str, ...]  当前所有合法着法，UCI 格式
state.history      # tuple[str, ...]  已经走过的着法
state.is_check     # bool 当前是否被将军
state.is_game_over # bool
state.result       # None 或 "1-0" / "0-1" / "1/2-1/2"
state.ply          # int  走了多少半步
state.last_error   # str | None  上一次被拒的原因（成功落子后为 None）
state.apply("e2e4")    # -> 新的 State（不修改原对象，可放心递归）
state.pretty()         # -> str，人类可读的棋盘，调试神器
```

> 取单格棋子用 `board.piece_at("e4")`（`'P'`/`'p'`/`'.'`）；`State` 只提供整张 `board` 矩阵。

> **为什么 `apply` 返回新对象**：学生写 minimax 要做"假设我走这步"的递归，不可变状态能避免整类"忘了撤销"的 bug。这是刻意的设计。

### `Agent`：你要实现的东西

```python
class Agent:
    name: str = "未命名"

    def choose_move(self, state: State) -> str:
        raise NotImplementedError

    # 以下都是可选的钩子，不实现也行
    def on_game_start(self, state: State, my_color: str) -> None: ...
    def on_game_end(self, result: str) -> None: ...
```

### `Game` / `Board`：AI 主动落子（"推"模式）

`choose_move` 是平台**问** AI 要一步棋（拉模式）。但学生经常需要反过来——自己算出结果后
**主动把棋子落到真实棋盘上**，尤其训练时想一边跑一边看。平台给你两个句柄：

```python
game  = arena.new_game(white=MyAgent(), black="builtin:minimax3")   # 对局：唯一写入口
board = game.board                                                   # 棋盘：只读视图
```

**走子（唯一写入口）**

```python
r = game.submit("e2e4")          # 唯一写法：UCI 字符串
if r == -1:
    print(r.reason)              # "非法着法：e2 的兵不能走到 e5"
```

> `board` 是**只读视图**，没有任何写方法。所有落子——AI 提交的、人类点击的——都走 `game.submit()`，
> 过裁判校验才生效。完整返回码与全部接口见《chessarena-API总表.md》。

**坐标转着法**：`uci(4, 1, 4, 3) -> "e2e4"`。别自己拼字符串。

**自定义起始局面**：`arena.new_game(..., fen="8/8/…")` 直接就从这个局面开局（残局、让子练习用）。

**细粒度读棋盘**

```python
board.get(x, y)        # -> 'P' / 'p' / '.' 
board.fen              # 整个局面
board.turn             # 'w' / 'b'
board.legal_moves      # ('e2e4', 'g1f3', ...)  tuple，顺序固定
```

**等对手（否则你的 while 循环会跑飞）**

```python
game.wait_my_turn(timeout=10)                              # 阻塞到轮到我；超时返回 False
game.on("opponent_move", lambda mv: print("对手走了", mv))  # 事件回调版（事件表见总表 §8）
```

### 三种运行模式：同一个对象，三种用法

| 模式 | 用途 | 要开浏览器吗 | 速度 |
|---|---|---|---|
| `live=True` | 调试、给人看、最终对战 | 要 | 每步 ~100–300ms（含落子动画） |
| `live=False` | 训练、self-play、跑联赛 | 不要 | 每秒数千步 |
| `live=False, record=True` | 无头跑 + 录像，事后回放 | 不要 | 同无头 |

```python
arena = Arena(live=True)                    # 落子真的画到页面上，棋子会动
arena = Arena(live=False)                   # 纯计算，不画，页面可以关掉
arena = Arena(live=False, record=True)      # 不画但录像（runs/<game_id>.jsonl），事后回放
```

**这就是"训练和最终对战都能操作该页面"的正解**：训练用 `live=False` 跑，否则浏览器渲染会成瓶颈
（慢 2–3 个数量级）；想看着它下就用 `live=True`；想事后复盘就 `record=True` 存事件流（页面内回放留作后续）。
**方法名、返回值和校验逻辑在三种模式下完全一致**——同一份 AI 代码，改一个参数就从"训练"切到"上台表演"。

### 两种接入位置

**同进程（推荐）**：学生 AI 是 Python 模块，被平台直接 import。

```python
from chessarena import Agent

class MyAgent(Agent):
    def choose_move(self, state):
        return self.search(state, depth=3)   # 扣模式：只返回着法，平台替你 submit
```

> 想自己落子（层 2）就写 `self.game.submit(best)`，**然后不要再 return 这个着法**——否则一步会走两次。
> 两种模式要么全程层 1，要么全程层 2。

**跨进程（AI 用别的语言、或在 GPU 机器上）**：方法名完全一样。

```python
from chessarena import Client
c = Client("http://127.0.0.1:8000", side="b")   # side 只影响 wait_my_turn
c.wait_my_turn(); c.submit("e2e4"); c.board().get(4, 3)
```

后端只需实现 3 个端点（`GET /state`、`POST /move`、`POST /reset`），用 `curl` 也能玩。

页面走的是本机 WebSocket（`/ws`）：每步落子推一条 `move`，终局推 `game_over`。消息格式与 HTTP 状态码见《API总表》§16——页面与 `Client` 读同一份快照，不会出现"两边各有一套状态"。

### 落子永远是受控的

AI 直接操作页面**不会把平台搞坏**，这是硬性保证：

- 非法着法 → 返回码 `-1`（跨进程为 HTTP 400 + 同一套返回码），**棋盘状态一字不变**（原子操作，不留半残局面）；可重试，默认 3 次。
- 不是你的回合 → 返回码 `-3`；对局已结束 → `-4`。
- 格式不对（SAN、大写、越界）→ 返回码 `-2`，与 `-1` 一样可重试。
- 重试 3 次仍失败、抛异常、返回 `None`、超时 → 该方判负（详见下表）。
- 所有落子都进日志（谁、第几步、耗时），联赛可追溯。

### 判定规则（写死，避免争议）

| 情况 | 判定 |
|---|---|
| 返回合法着法 | 正常落子 |
| 返回非法着法 | 同一步内**允许重试**，最多 3 次（共享同一个 3.0s 预算） |
| 3 次都被拒 | `game.on_retry_exhausted` 决定：`forfeit` 判负（默认）/ `random` 替走一步 |
| 抛异常 | 该方判负，异常堆栈写进日志 |
| 单步超过 `timeout`（默认 3.0s，含全部重试） | 该方判负，提示"超时" |
| 返回 None / 空字符串 | 该方判负 |
| 人类点错 | 棋子弹回并提示原因，**不消耗重试次数**，可无限重试 |
| 双方都无法将死（子力不足）/ 三次重复 / 50 步 | 自动判和 |

> 超时可以在 `config.yaml` 里按 AI 单独放宽（比如神经网络那组给 10s），但**联赛里所有 AI 用同一个值**，保证公平。

### 调试建议（写在作业文档里）
- 先实现 `choose_move` 返回 `state.legal_moves[0]`，确认能下棋、不判负，再加搜索。
- 用 `state.pretty()` 在终端打印，比看网页快。
- 用 `chessarena test --games 20` 量化，别靠感觉。
- 日志在 `runs/<时间戳>/`：每步的 fen、你的返回值、耗时。

---

## 五、配置文件 `config.yaml`

```yaml
server:
  host: 127.0.0.1        # 想给全班访问就改 0.0.0.0
  port: 8000

game:
  timeout: 3.0              # 每步总时长（秒，含全部重试）
  max_retries: 3            # 一步最多被拒几次
  on_retry_exhausted: forfeit   # forfeit 判负 / random 替走一步
  on_timeout: forfeit           # 超时处置

league:
  rounds: 2              # 每个 AI 互相打几轮
  openings: 8            # 随机开局库前 8 步，防止所有对局一模一样
  max_concurrent: 4      # 并发跑几盘（多进程，吃满 CPU）

builtin: [random, greedy, minimax2, minimax3, stockfish]
```

> 键的完整语义见《API总表》§13。v1 不提供整盘时间控制（`300+2` 那种），只有每步 `timeout`。

---

## 六、目录结构（学生只需要关心 `agents/`）

```
ChessArena/                    # 项目根（仓库名）
├── chessarena/                # 平台本体
│   ├── core/                  # 裁判 Game、Board、State、Agent、Arena、录像、外部对手
│   ├── builtin/               # 五档内置（random / greedy / minimax2 / minimax3 / stockfish）
│   ├── engines/               # UCI 引擎适配
│   ├── web/                   # FastAPI 服务 + WebSocket
│   │   └── ui/                # 页面：index.html / app.js / style.css
│   ├── league.py              # 循环赛 + ELO + HTML 报告
│   ├── client.py              # 跨进程 Client
│   └── cli.py                 # play / serve / test / league / replay
├── vendor/chessground/        # 前端预构建产物（零构建，直接引）
├── thirdparty/                # chessground 源码克隆 + Stockfish（已解压）
├── tests/                     # unittest：内核 / 服务 / 前端接线 / 联赛 / 外部对手
├── runs/                      # 录像 runs/<game_id>.jsonl、自评 JSON
├── results/                   # 联赛报告（results/league-*/index.html + pgn/）
├── agents/                    # ★ 学生把自己的 AI 放这里（examples/ 有 3 个样例）
├── assignments/               # ★ 作业骨架（eval/minimax）与 grade.py 评分脚本
├── config.yaml                # 端口、每步时限、重试、联赛参数
└── start.bat                  # Windows 一键启动
```

---

## 七、怎么用在一学期的课上（建议节奏）

| 周次 | 内容 | 用平台做什么 |
|---|---|---|
| 第 1 周 | 跑通环境 | 发 `random_agent.py`，让它在网页上跟 L1 下起来 |
| 第 2 周 | 评估函数 | 改子力价值表，跟 L2 贪心打，胜率进班级榜 |
| 第 3 周 | minimax | `assignments/minimax_stub.py` 补全递归，跟 L3 打 |
| 第 4 周 | alpha-beta | 看 `builtin/minimax3.py` 那十几行剪枝，然后跟 L4 打 |
| 第 5–6 周 | 迭代加深 / 置换表 / 着法排序 | 自由发挥，随时用 `test` 命令自测 |
| 第 7 周 | 联赛 | 全班跑一轮联赛，生成 ELO 榜，学生上台讲自己的思路 |

平台自带 `assignments/` 里就有每阶段的骨架文件和评分脚本，你只需要指定当周要跑哪个。

---

## 八、成品包含 / 暂不包含

**v1 会有的**
- ✅ 网页 UI（棋盘、动画、记谱、评估条、升变、悔棋、翻转、PGN 导出）
- ✅ 人机（5 档）、机机观战（可调速/暂停/单步）、学生 AI vs 内置、联赛
- ✅ **AI 双向控制**：被平台调用（`choose_move`）+ 主动落子（`game.submit()`），`live` / `live=False`（无头）/ `record` 三种运行模式
- ✅ 三种 AI 接入方式（同进程 Python 类 / UCI 引擎 / 跨进程 HTTP 客户端）
- ✅ 完整 API 文档 + 3 个可运行样例 + 作业骨架
- ✅ 联赛 ELO 报告、每局 PGN、日志
- ✅ 中文界面

**v1 不做（按需求明确排除）**
- ❌ 联机对战 —— 单机即可，不做 WebSocket 房间，也不做账号/数据库
- ❌ 手机端专门适配（能打开，但按钮偏小）
- ❌ 开局库、残局库、Syzygy 表库（可以让 Stockfish 那一档自带）
- ❌ 强化学习训练循环（这是 `PettingZoo` 那条路线的事，平台只提供"评测场"）

---

## 九、常见问题

**Q：`serve` 报端口被占用？**
A：`config.yaml` 里改 `port: 8001`，或 `python -m chessarena serve --port 8001`。

**Q：网页上点了棋子没反应？**
A：棋盘变灰说明对局已结束；或者轮到 AI 走、你在点自己的子。

**Q：网页上点了棋子没反应，或者 AI 一直不走？**
A：先看状态栏：显示"黑方思考中…"说明服务端正在算，等 3 秒；如果长时间不动，页面会在 5 秒内自动用 HTTP 把局面校准回来。仍不行时看服务器终端有没有 `[chessarena]` 开头的日志，浏览器按 F12 看控制台；`GET /debug` 会给出驱动线程状态、空转次数与最近一次异常。

**Q：学生的 AI 一步要 30 秒，一直判负。**
A：`python -m chessarena serve --timeout 10`，或改 `config.yaml` 的 `game.timeout`。但**别只为自己的 AI 调**——联赛里所有 AI 同一标准。

**Q：L5 的 Stockfish 打不开？**
A：引擎已随包放在 `thirdparty/stockfish/stockfish-windows-x86-64-universal.exe`（zip 解压即可）。找不到时按顺序取：环境变量 `CHESSARENA_STOCKFISH` → 该默认路径。棋力用 `CHESSARENA_STOCKFISH_ELO=1800`（1320–3190），每步用时用 `CHESSARENA_STOCKFISH_MOVETIME=0.6`。不想用就把 `builtin:stockfish` 从对局双方里换掉。

**Q：前端能改吗？**
A：`chessarena/web/ui/` 是三个静态文件（chessground 的预构建产物从 `/vendor` 引），没有任何构建步骤。改样式直接改 `style.css`，改交互改 `app.js`，刷新即生效。

**Q：能换成中国象棋吗？**
A：架构里规则层是插件，换棋种只需要新增一个 `Game` 实现（着法生成、胜负判定、FEN 表示）。UI 的棋盘渲染是独立组件，但要重画棋盘格线和棋子字形。这是 v2 的事。
