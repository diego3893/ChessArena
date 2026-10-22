# ChessArena 棋盘与裁判 · API 规格 v1

> 这份文档定义**棋盘这边**的全部接口：AI 怎么读局面、怎么落子、落错了拿到什么。
> 面向对象：平台实现者 + 给学生写调用约定的助教。学生只需要看第 6 节和第 9 节。

---

## 1. 三条设计原则

1. **裁判（`Game`）是唯一真相源。** 棋盘状态只由裁判产生，任何人不能改。
2. **只有一个写入口：`submit()`。** AI 落子、人点鼠标，走的是同一个函数、同一套校验。
3. **读接口只读且不可变。** `state` / `board` 拿到的都是快照，随便存、随便递归，不会影响真实对局。

```
   AI 算出着法 ─┐
                ├─→  Game.submit()  ─→  Result(0)  ─→  规则更新  ─→  推送到页面
   人点击棋盘  ─┘        ↑                                              ↓
                   校验合法性                                  Board 只读视图 / 动画
                         │
                    Result(-1) ─→ 退回给调用方，让 AI 重新落子
```

---

## 2. 坐标与着法表示

**坐标**：`x` = 列 0–7（a–h），`y` = 行 0–7（第 1–8 横线，**从下往上**）

```
 y=7  ♜ ♞ ♝ ♛ ♚ ♝ ♞ ♜      8
 y=6  ♟ ♟ ♟ ♟ ♟ ♟ ♟ ♟      7
 y=1  ♙ ♙ ♙ ♙ ♙ ♙ ♙ ♙      2
 y=0  ♖ ♘ ♗ ♕ ♔ ♗ ♘ ♖      1
      x=0 ...         x=7     a ... h
```

**着法只有一个标准格式：UCI 字符串**（小写，`起点+终点`，升变加子）

| 例子 | 含义 |
|---|---|
| `"e2e4"` | e2 走到 e4 |
| `"g1f3"` | 马从 g1 到 f3 |
| `"e7e8q"` | e7 兵升变到 e8，升为后（`q`/`r`/`b`/`n`） |
| `"e1g1"` | 王车易位（王从 e1 到 g1，就是这个写法） |

不接受的写法：`"e2-e4"`、`"e4"`、`"Nf3"`（SAN）、`"E2E4"`（大写）。
**不用 SAN 是故意的**：SAN 有歧义（两个马都能到 f3 时只写 Nf3 不够），UCI 无歧义、可逆、能直接和 FEN/PGN 互转。

需要坐标转字符串时用工具函数，别自己拼：

```python
from chessarena import uci
uci(4, 1, 4, 3)        # -> "e2e4"
uci(4, 6, 4, 7, "q")   # -> "e7e8q"
```

---

## 3. 返回码

`submit()` 返回一个 `Result` 对象，**所有失败都只是返回码，不抛异常、不改棋盘状态**。

| code | 常量名 | 含义 | AI 该做什么 |
|---|---|---|---|
| `0` | `OK` | 落子成功 | 继续 |
| `-1` | `ILLEGAL_MOVE` | 格式对，但这步不合法（走法不对 / 目标被己方占 / 会导致自己被将军） | 换一步重给 |
| `-2` | `BAD_FORMAT` | 字符串就不是合法着法（长度、字符、坐标越界） | 修 bug 重给 |
| `-3` | `NOT_YOUR_TURN` | 现在不轮到你 | 先 `wait_my_turn()` |
| `-4` | `GAME_OVER` | 对局已结束 | 停止 |

`Result` 既能当布尔用，也能直接和整数比：

```python
r = game.submit("e2e4")

if r:              # 推荐写法：True 表示成功
    ...
if r == -1:        # 也可以：给学生看的是这个数字
    print(r.reason)   # "非法着法：e2 的兵不能走到 e5"
if r.code == -1:   # 等价
    ...
```

`Result` 的属性：`.ok`(bool) `.code`(int) `.reason`(str，中文人话，可直接 print 给学生)。

> **为什么不用异常**：学生代码里异常一多就没人调了；返回码能让他们在循环里"打日志-重试-看结果"。
> 需要严格模式时 `game.submit(move, strict=True)` 会抛 `IllegalMoveError`，默认不开。

---

## 4. 写接口

```python
game.submit(move: str, *, strict: bool = False) -> Result
```

- 唯一写入口。AI 调用、人类点击最终都进这里。
- **原子性**：返回非 0 时，棋盘状态、轮次、时钟、历史全部不变。
- 成功后：更新局面 → 检查终局（将杀/逼和/三次重复/50 步）→ 广播事件给页面。

**人类路径的差异（只有一处）**：人类点错了不算"尝试次数"，棋子直接弹回并提示原因，可以无限重试（只受时钟限制）。因为手滑是常态，而 AI 连错三次通常是代码有 bug。

---

## 5. 读接口

### `game`（对局层）

```python
game.state          # State 快照（见下）
game.board          # Board 只读视图
game.turn           # 'w' / 'b'
game.over           # bool
game.result         # None / '1-0' / '0-1' / '1/2-1/2'
game.over_reason    # 'checkmate' / 'stalemate' / 'threefold' / 'fifty' / 'insufficient' / 'resign' / 'timeout' / 'retry_exhausted'
game.history        # ['e2e4', 'e7e5', ...]  已走过的着法
game.ply            # 走了多少半步
game.wait_my_turn(timeout=10.0) -> bool     # 阻塞到轮到我；超时返回 False
game.on("opponent_move", lambda mv: print("对手走了", mv))   # 事件回调（事件表见总表 §8）
game.pgn()          # 导出 PGN 文本
```

### `board`（棋盘层，只读）

```python
board.get(x, y)              # -> 'P' / 'p' / '.'（大写=白，小写=黑）
board.piece_at("e4")         # -> 'P' / 'p' / '.'（大写=白，小写=黑）
board.fen                    # 当前 FEN
board.legal_moves            # ['e2e4', 'g1f3', ...]  当前全部合法着法
board.moves_from("e2")       # -> ['e3', 'e4']  某个子的可走格（做 UI 高亮/教学用）
board.matrix()               # 8x8 二维列表，可直接 np.array(...) 喂网络
board.ascii()                # 打印成字符画，终端调试用
```

### `state`（给 AI 的完整快照，一次拿全）

```python
state.board        # 同 board.matrix()
state.fen
state.turn
state.legal_moves
state.history
state.ply
state.is_check     # 当前是否被将军
state.last_error   # ★ 上一次被拒的原因（字符串），成功的回合为 None
```

`state.last_error` 是重试机制的关键：AI 被拒之后，下一轮调用时能从这里读到"你上次为什么不行"。

---

## 6. 学生怎么用（两种，第二种才是主角）

### 层 1：只实现 `choose_move`（90% 的学生）

平台负责调用、重试、落子。学生不碰返回码。

```python
from chessarena import Agent

class MyAgent(Agent):
    name = "张同学"

    def choose_move(self, state) -> str:
        if state.last_error:                  # 上次被拒了，可以据此纠正
            print("被拒：", state.last_error)
        return state.legal_moves[0]
```

### 层 2：自己驱动（要控制循环、或训练时）

```python
game = arena.new_game(white=MyAgent(), black=BlackAgent())

while not game.over:
    if not game.wait_my_turn(timeout=10):
        break
    move = my_search(game.state)
    r = game.submit(move)
    if r == -1:
        my_log.append((game.state.fen, move, r.reason))   # 记下来，赛后分析
```

两种方式可以混用：`choose_move` 里也可以直接 `self.game.submit(...)`，
但**不要**在 `choose_move` 里 submit 之后再返回一个着法，会导致走两步。这条要写进调用约定里。

---

## 7. 重试、超时、判负（你问的那个"返回 -1 让它重来"，必须配这道闸）

只给 -1 不给上限，一个死循环的 AI 会把整节课卡死。所以规则是：

| 项 | 默认 | 说明 |
|---|---|---|
| `max_retries` | 3 | 一步棋最多被拒 3 次，第 4 次拒绝即触发处置 |
| 重试是否计时 | 是 | **所有尝试共享同一个时钟预算**，不能靠重试"白嫖"思考时间 |
| `timeout`（每步） | 3.0s | 含全部重试；超时直接判负（超时拿不到返回值，所以不是返回码） |
| `on_retry_exhausted` | `forfeit` | 重试用完：`forfeit` 判负 / `random` 替它随便走一步（课堂演示建议 `random`，别让演示卡住） |
| `on_timeout` | `forfeit` | 超时判负 |

所有被拒都写日志（fen、提交的字符串、返回码、耗时），并在联赛报告里汇总成一列 **"非法率"**。
这一列在教学上很有用：非法率 40% 的学生，基本是没读合法着法列表、在自己瞎猜。

---

## 8. 运行模式

同一个 `arena` 对象，一个参数切换：

```python
arena = Arena(live=True)                   # 落子实时画到页面，有动画
arena = Arena(live=False)                  # 无头：训练/self-play/联赛，每秒数千步
arena = Arena(live=False, record=True)     # 无头跑 + 录像，事后再在页面上回放
```

方法名、返回值、校验逻辑三种模式**完全一致**。训练用同一份 AI 代码，切到 `live=True` 就能上台。

---

## 9. 最小可运行示例（可以直接发给学生）

```python
import chessarena
from chessarena import Agent

class MyAgent(Agent):
    name = "样例-AI"

    def choose_move(self, state):
        # 1) 先保证不崩：随便找个合法着法
        if not state.legal_moves:
            return None
        # 2) 在这里写你的搜索
        return state.legal_moves[0]


if __name__ == "__main__":
    arena = chessarena.Arena(live=True)          # 改成 False 就是无头训练
    game = arena.new_game(white=MyAgent(), black="builtin:minimax3")
    game.run_to_end()                            # 自动跑到分出胜负
    print(game.result, game.over_reason)
    print(game.pgn())
```

---

## 10. 平台保证（写进调用约定，避免学生争论）

1. **原子性**：`submit` 失败时，局面、轮次、时钟、历史一样都不变。
2. **顺序性**：同一时刻只有轮到的一方可以 `submit`，另一方拿到 `-3`。
3. **可重放**：所有成功落子都进 `history` 与 PGN，同一起始局面必然复现同一局棋。
4. **隔离性**：跑联赛时多个对局在不同进程，任何一方崩溃不影响其他对局，只记该局判负。
5. **确定性**：给定 FEN 和着法，`board` 的返回永远相同；`legal_moves` 顺序固定（可用于哈希）。

---

## 11. 常见问题（给学生）

**Q：为什么我返回 `"Nf3"` 被判 `-2`？**
A：不接受 SAN。用 `state.legal_moves` 里的字符串，或 `uci(6,0,5,2)`。

**Q：为什么走法看着对却 `-1`？**
A：可能是走了之后自己王被将军。用 `board.moves_from(sq)` 先筛，或者干脆只在 `state.legal_moves` 里挑。

**Q：`state` 我能存下来慢慢算吗？**
A：能。它是快照，不会被别人改。`state.apply(move)` 也能拿新快照（本地模拟用，不影响真实对局）。

**Q：我能在 `choose_move` 里调用 `submit` 吗？**
A：技术上能，但不推荐——那是层 2 的用法。混用容易一步走两次。要么全程层 1，要么全程层 2。
