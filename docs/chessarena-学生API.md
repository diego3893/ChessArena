# ChessArena 学生 API

> **只看这一页就够写 AI 了。** 这里只列学生用得到的接口；平台内部接口、推送协议、引擎注册见
> [《API 总表》](chessarena-API总表.md)（SSOT）。
> 平台版本：0.1.0-dev。

---

## 0. 先记住四条

1. **落子只有一个入口**：`game.submit(move)`。你返回着法、或自己调用它，都要过裁判校验。
2. **着法只有一种格式**：UCI 字符串，小写、起终点、升变带子 —— `"e2e4"`、`"g1f3"`、`"e7e8q"`。
   不接受 `"Nf3"`（SAN）、`"E2E4"`（大写）、`"e2-e4"`。
3. **失败不抛异常，只返回错误码**：`-1` / `-2` 可以换一步重试，`-3` 不是你的回合，`-4` 已经结束。
4. **每步 3 秒、最多被拒 3 次**：所有重试共享同一个 3 秒预算（默认值，见 `config.yaml`）。

---

## 1. 五分钟上手

```python
from chessarena import Agent

class MyAgent(Agent):
    name = "我的 AI"                     # 显示在页面上的名字

    def choose_move(self, state):
        return state.legal_moves[0]      # 先能下棋，再写搜索
```

把它保存成 `agents/my_agent.py`，刷新页面就能在下拉框里选到它。

---

## 2. `Agent`：你要实现的类

| 成员 | 类型 / 签名 | 必须 | 说明 |
|---|---|---|---|
| `name` | `str` | 建议 | 显示名 |
| `choose_move(state)` | `-> str \| None` | ✅ | 返回 UCI 着法；返回 `None` 视为弃权判负 |
| `on_game_start(state, color)` | `-> None` | ❌ | 开局钩子，`color` 是 `"w"` / `"b"` |
| `on_game_end(result)` | `-> None` | ❌ | 终局钩子，`result` 是 `"1-0"` / `"0-1"` / `"1/2-1/2"` |
| `on_opponent_move(move)` | `-> None` | ❌ | 对手每走一步回调一次 |
| `self.game` | `Game` | 平台注入 | 想自己落子（层 2）时用它 |
| `self.color` | `"w"` / `"b"` | 平台注入 | 你执哪边 |
| `self.seed` | `int` | 平台注入 | 需要随机数时用它建 `random.Random(self.seed)`，保证可复现 |

---

## 3. `State`：你看到的世界（只读快照）

| 成员 | 类型 | 说明 |
|---|---|---|
| `fen` | `str` | 标准 FEN |
| `turn` | `"w"` / `"b"` | 当前走子方 |
| `board` | `8×8 tuple` | `board[0]` 是第 8 横线；`"P"` 白兵、`"p"` 黑兵、`"."` 空 |
| `legal_moves` | `tuple[str, ...]` | 当前全部合法着法（UCI，顺序固定） |
| `history` | `tuple[str, ...]` | 已经走过的着法 |
| `ply` | `int` | 走了多少半步 |
| `is_check` | `bool` | 当前是否被将军 |
| `is_game_over` | `bool` | 对局是否结束 |
| `result` | `str \| None` | `"1-0"` / `"0-1"` / `"1/2-1/2"` / `None` |
| `last_error` | `str \| None` | **上一次被拒的原因**（成功落子后为 `None`） |
| `apply(move)` | `-> State` | 本地推演一步，返回**新快照**，不影响真实对局；非法时抛 `IllegalMoveError` |
| `pretty()` | `-> str` | 终端可读棋盘，调试用 |
| `copy()` | `-> State` | 快照本身不可变，一般不需要 |

`State` 是不可变的：可以放心存下来、递归下去，不会影响真实对局。

```python
for move in state.legal_moves:
    child = state.apply(move)        # 新快照
    score = evaluate(child)          # 你的评估
```

---

## 4. `Result` 与返回码

| 成员 | 类型 | 说明 |
|---|---|---|
| `ok` | `bool` | `code == 0` |
| `code` | `int` | 见下表 |
| `reason` | `str` | 中文人话，可直接 `print` 给学生 |
| `move` | `str \| None` | 被接受的规范化着法 |

`Result` 能当布尔用，也能直接和整数比：

```python
r = game.submit("e2e4")
if r:            print("成功")
if r == -1:      print("非法：", r.reason)
```

| code | 含义 | 你该做什么 |
|---|---|---|
| `0` | 成功 | 继续 |
| `-1` | 非法着法（格式对，但走不通/走完自己被将军） | 换一步 |
| `-2` | 格式不对（SAN / 大写 / 越界 / 长度不对） | 修 bug |
| `-3` | 不是你的回合 | 先 `game.wait_my_turn()` |
| `-4` | 对局已结束 | 停止 |

---

## 5. `Game`：主动落子、等对手

| 成员 | 签名 | 说明 |
|---|---|---|
| 落子 | `submit(move, *, strict=False)` | 唯一写入口，返回 `Result` |
| 局面快照 | `state` | 返回 `State` |
| 只读棋盘 | `board` | 返回 `Board`（见第 6 节） |
| 走子方 | `turn` | `"w"` / `"b"` |
| 是否结束 | `over` | `bool` |
| 结果 | `result` / `over_reason` | `"1-0"`… / `"checkmate"`、`"timeout"`… |
| 历史 | `history` / `ply` | 已走着的 UCI 序列 / 半步数 |
| 等回合 | `wait_my_turn(*, timeout=10.0)` | 阻塞到轮到你；超时返回 `False` |
| 事件 | `on(event, callback)` | 见下表 |
| 认输 | `resign(side=None)` | 缺省为当前走子方 |
| 悔棋 | `undo(n=1)` | 回退 `n` 个半步 |
| 剩余时间 | `clock(side=None)` | 当前这一步还剩多少秒 |
| 导出 | `pgn()` | PGN 文本 |

**事件**（`game.on(...)`）：

| 事件 | 回调参数 | 何时 |
|---|---|---|
| `move` | `(move, result)` | 任何一方成功落子 |
| `illegal` | `(move, result)` | 落子被拒 |
| `opponent_move` | `(move)` | 对手成功落子 |
| `game_over` | `(result, reason)` | 终局 |
| `timeout` | `(side, seconds)` | 某方超时 |
| `retry` | `(side, attempt, result)` | 某方第 n 次被拒 |

### 两种写法，别混用

```python
# 层 1（推荐）：只返回着法，平台替你 submit
def choose_move(self, state):
    return self.search(state)

# 层 2：自己落子，然后 return None
def choose_move(self, state):
    best = self.search(state)
    self.game.submit(best)
    return None
```

> 平台会检测"这一步你已经自己 submit 过了"：此时你返回什么都会被忽略，不会走两步。
> 但仍然建议**全程只用一种写法**——混着写时，读代码的人（和未来的你）很难判断这一步到底是谁落的。

---

## 6. `Board`：只读棋盘（可选）

`game.board` 是一个只读视图，**没有任何写方法**。

| 成员 | 签名 | 返回 |
|---|---|---|
| 按坐标取子 | `get(x, y)` | `"P"` / `"p"` / `"."`（`x` 列 0–7，`y` 行 0–7） |
| 按格取子 | `piece_at("e4")` | 同上 |
| 某子可走 | `moves_from("e2")` | `["e3", "e4"]` |
| 局面 | `fen` / `turn` | `str` |
| 合法着法 | `legal_moves` | `tuple[str, ...]` |
| 矩阵 | `matrix()` | 8×8 `list[list[str]]`，可直接 `np.array()` |
| 字符画 | `ascii()` | `str` |

---

## 7. `Client`：AI 跑在别的进程/机器上

方法与同进程完全同名、同返回：

```python
from chessarena import Client

c = Client("http://127.0.0.1:8000", side="b")   # side 只影响 wait_my_turn
c.wait_my_turn(timeout=10)
state = c.state()
r = c.submit(state.legal_moves[0])
if r == -1:
    print(r.reason)
```

| 成员 | 说明 |
|---|---|
| `Client(base_url, *, timeout=10.0, side=None)` | `side` 为 `"w"` / `"b"` |
| `.state()` / `.board()` | 返回 `State` / `Board` |
| `.legal_moves()` | 返回 `tuple[str, ...]` |
| `.submit(move)` | 返回 `Result`，与同进程同码同因 |
| `.wait_my_turn(timeout=10.0)` | 轮询到轮到自己 |
| `.reset(fen=None)` | 重开 |

---

## 8. 工具函数与常量

```python
from chessarena import uci, square, xy, START_FEN, RC

uci(4, 1, 4, 3)        # "e2e4"   （x1, y1, x2, y2, promo="")
uci(4, 6, 4, 7, "q")   # "e7e8q"
square(4, 1)           # "e2"
xy("e2")               # (4, 1)
START_FEN              # 初始局面
RC.ILLEGAL_MOVE        # -1
```

---

## 9. 训练模式（无头，同一套代码）

```python
import chessarena

arena = chessarena.Arena(live=False)                  # 不画页面，每秒数千步
game = arena.new_game(white=MyAgent(), black="builtin:minimax3")
game.run_to_end(max_plies=400)
print(game.result, game.over_reason, game.ply)
print(game.pgn())
arena.close()
```

想自己驱动、边跑边看：

```python
while not game.over:
    if not game.wait_my_turn(timeout=10):
        break
    move = my_search(game.state)
    if game.submit(move) == -1:
        print("被拒：", game.state.last_error)
```

`live=True` 只影响"要不要把落子推到页面"：同一份 AI 代码，在 `python -m chessarena serve` 下
每个 `game.submit()` 都会画到网页上，换成 `live=False` 就是纯计算、每秒数千步。

---

## 10. 时间、重试与判负

| 项 | 默认 | 说明 |
|---|---|---|
| 每步时限 | `3.0s` | **含全部重试**，超时判负 |
| 最多被拒 | `3` 次 | 第 4 次拒绝按 `on_retry_exhausted` 处置（默认判负） |
| 返回 `None` | — | 判负 |
| 抛异常 | — | 判负，异常写进日志 |
| 人类点错 | — | 不消耗重试次数（只受时钟限制） |
| 三次重复 / 50 步 / 子力不足 | — | 自动判和 |

这些值在 `config.yaml` 的 `game:` 段里改；联赛里所有 AI 用同一套。

---

## 11. 常见错误对照

| 你写的 | 结果 | 怎么改 |
|---|---|---|
| `return "Nf3"` | `-2` 格式错 | 用 `state.legal_moves` 里的字符串，或 `uci(...)` |
| `return "E2E4"` | `-2` | 小写 |
| `return "e2-e4"` | `-2` | 不要连字符 |
| `return None` / `""` | 判负 | 至少返回 `state.legal_moves[0]` |
| `self.game.submit(m); return m` | 只落一次（返回的 `m` 被忽略） | 能跑，但建议全程只用一种写法 |
| `state.apply("e2e5")` | 抛 `IllegalMoveError` | 先查 `state.legal_moves` |
| `board.get(4, 3) = "Q"` | `AttributeError` | `Board` 只读，落子走 `game.submit()` |
| 每步算 10 秒 | 超时判负 | 降深度 / 加剪枝；`config.yaml` 调 `game.timeout` |

---

## 12. 自测、评分与联赛

```bash
# 跟内置对手打 20 盘：胜率、平均每步、最长一步
python -m chessarena test agents/my_agent.py --vs builtin:greedy --games 20

# 跟同学的 AI 打
python -m chessarena test agents/my.py --vs agents/li.py --games 10

# 自评脚本（写一份 runs/grade-<名字>.json）
python assignments/grade.py agents/my_agent.py --games 12

# 全班联赛（ELO + 非法率 + 每局 PGN）
python -m chessarena league --players random,greedy,minimax2,agents/my.py --rounds 2
```

---

## 13. 三种接入方式（细节见总表 §15）

| 方式 | 适合 | 写法 |
|---|---|---|
| 同进程 Python 类 | 90% 的学生 | `agents/my_agent.py` 里继承 `Agent` |
| UCI 引擎 | C++/Rust/Java | `agents/agents.json` 注册 `{"type":"uci","cmd":[...]}` |
| HTTP 服务 | 远程 / 用 GPU | `{"type":"http","url":"http://…/move"}`，或有 `Client` |

> 完整字段、UCI 握手、HTTP JSON 见 [《API 总表》§15](chessarena-API总表.md)。
