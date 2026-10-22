# ChessArena 完整 API 总表 v1

> 全部对外接口的单一事实来源（single source of truth）。本文档与《chessarena-API规格.md》冲突时，以本文档为准。
> 约定：**R** = 只读，**W** = 写入真相源，**B** = 阻塞调用。

## 0. 对象索引

| 对象 | 怎么拿到 | 职责 | 可变性 |
|---|---|---|---|
| `Arena` | `Arena(...)` | 环境装配：运行模式、内置对手、开新局、跑联赛 | — |
| `Game` | `arena.new_game(...)` | **裁判**：唯一真相源、唯一写入口 | 只有它能改局面 |
| `Board` | `game.board` | 棋盘只读视图（给 AI 和 UI 看） | 只读 |
| `State` | `game.state` | 一次拿全的快照（含 `last_error`） | 只读 |
| `Result` | `game.submit()` 返回 | 返回码 + 人话原因 | 只读 |
| `Agent` | 学生继承 | AI 基类 | — |
| `Client` | `Client(url)` | 跨进程同构客户端 | — |
| `League` | `arena.league(...)` | 循环赛 + ELO | — |

---

## 1. `Arena`

| 成员 | 签名 | 说明 |
|---|---|---|
| 构造 | `Arena(*, live=True, record=False, seed=None, config="config.yaml")` | `live` 决定是否把落子推给页面；`record` 无头运行但录像 |
| 开新局 | `new_game(*, white, black, fen=None, timeout=None, max_retries=None, game_id=None) -> Game` | `white`/`black` 见 §10 |
| 联赛 | `league(players, *, rounds=2, openings=8, max_concurrent=4) -> League` | `players` 是选手列表 |
| 内置对手 | `builtins() -> list[str]` | 返回 `["random","greedy","minimax2","minimax3","stockfish"]` |
| 已加载 AI | `agents() -> list[AgentInfo]` | 扫描 `agents/` 目录，`AgentInfo` 有 `.name .path .class_name` |
| 加载 | `load_agent(path_or_module) -> Agent` | 手动加载，热更新用 |
| 关闭 | `close()` | 释放 Stockfish 子进程、关闭页面推送 |

---

## 2. `Game`（裁判）

### 2.1 写入口

| 成员 | 签名 | 返回 | 说明 |
|---|---|---|---|
| 落子 | `submit(move, *, strict=False)` | `Result` | **唯一写入口**。AI 与人类共用。失败不改任何状态 |
| 认输 | `resign(side=None)` | `Result` | 缺省为当前走子方 |
| 悔棋 | `undo(n=1)` | `bool` | 人机模式自动退到上一次己方回合 |
| 重开 | `reset(fen=None)` | `None` | 清空历史，回到指定局面 |

### 2.2 状态读取

| 成员 | 类型 | 说明 |
|---|---|---|
| `state` | `State` | 完整快照（§4） |
| `board` | `Board` | 棋盘视图（§3） |
| `turn` | `"w"` / `"b"` | 当前走子方 |
| `over` | `bool` | 是否结束 |
| `result` | `None` / `"1-0"` / `"0-1"` / `"1/2-1/2"` | 白视角 |
| `over_reason` | `str` | `checkmate`/`stalemate`/`threefold`/`fifty`/`insufficient`/`resign`/`timeout`/`retry_exhausted` |
| `history` | `list[str]` | 已走着的 UCI 序列 |
| `ply` | `int` | 半步数 |
| `white` / `black` | `Agent` | 双方对象 |
| `game_id` | `str` | 唯一标识，用于日志与录像文件命名 |

### 2.3 控制与事件

| 成员 | 签名 | 说明 |
|---|---|---|
| 等回合 | `wait_my_turn(*, timeout=10.0) -> bool` **B** | 阻塞到轮到自己；超时返回 `False`。层 2 必用 |
| 跑到结束 | `run_to_end(*, max_plies=1000) -> str` **B** | 自动驱动双方到终局，返回 `result` |
| 单步 | `step() -> Result` **B** | 让当前走子方走一步（观战"单步"用） |
| 事件 | `on(event, callback)` | 事件名见 §8 |
| 时钟 | `clock(side=None) -> float` | 剩余秒数 |
| 导出 | `pgn() -> str` / `to_json() -> dict` | 棋谱 / 全量状态 |

---

## 3. `Board`（只读棋盘）

| 成员 | 签名 | 返回 | 说明 |
|---|---|---|---|
| 取子 | `get(x, y)` | `"P"` / `"p"` / `"."` | 大写白、小写黑 |
| 按格取 | `piece_at("e4")` | 同上 | |
| 局面 | `fen` | `str` | 属性 |
| 合法着法 | `legal_moves` | `list[str]` | 顺序固定，可用于哈希 |
| 某子可走 | `moves_from("e2")` | `list[str]` | 目标格，如 `["e3","e4"]`，UI 高亮/教学用 |
| 矩阵 | `matrix()` | `8x8 list[list[str]]` | 行序从黑方底线开始，可直接 `np.array()` |
| 字符画 | `ascii()` | `str` | 终端调试 |
| 是否被将 | `is_check` | `bool` | 属性 |
| 空着手 | `is_empty(x, y)` | `bool` | |

> `Board` **没有任何写方法**。这是刻意的：唯一写入口是 `Game.submit()`。

---

## 4. `State`（快照）

| 成员 | 类型 | 说明 |
|---|---|---|
| `board` | `8x8 list` | 同 `board.matrix()` |
| `fen` | `str` | |
| `turn` | `"w"` / `"b"` | |
| `legal_moves` | `list[str]` | |
| `history` | `list[str]` | |
| `ply` | `int` | |
| `is_check` | `bool` | |
| `is_game_over` | `bool` | 对局是否已结束（与 `game.over` 同值） |
| `result` | `str \| None` | `"1-0"` / `"0-1"` / `"1/2-1/2"` / `None`（白视角，与 `game.result` 同值） |
| `last_error` | `str \| None` | ★ **上一次被拒的原因**。成功的回合为 `None`。层 1 重试靠它 |
| `apply(move)` | `-> State` | 本地沙盘推演，**不影响真实对局**；非法时抛 `IllegalMoveError` |
| `pretty()` | `str` | 终端可读棋盘（= `board.ascii()`），调试用 |
| `copy()` | `-> State` | 深拷贝（一般不需要，快照本身不可变） |

> 取单格棋子用 `board.piece_at("e4")`；`State` 不重复提供 `piece_at`，避免两处实现漂移。

---

## 5. `Result`

| 成员 | 类型 | 说明 |
|---|---|---|
| `ok` | `bool` | `code == 0` |
| `code` | `int` | 见下表 |
| `reason` | `str` | 中文人话，可直接 `print` 给学生 |
| `move` | `str \| None` | 被接受的规范化着法 |
| `__bool__` | — | `bool(result)` 等价 `result.ok` |
| `__eq__` | — | `result == -1` 可与整数直接比较 |

### 返回码表

| code | 常量 | 含义 | AI 该做什么 |
|---|---|---|---|
| `0` | `RC.OK` | 成功 | 继续 |
| `-1` | `RC.ILLEGAL_MOVE` | 格式对但这一步不合法（含走完自己被将军） | 换一步 |
| `-2` | `RC.BAD_FORMAT` | 不是合法着法串（长度/字符/越界） | 修 bug |
| `-3` | `RC.NOT_YOUR_TURN` | 不轮到你 | 先 `wait_my_turn()` |
| `-4` | `RC.GAME_OVER` | 对局已结束 | 停止 |

---

## 6. `Agent`（学生基类）

| 成员 | 签名 | 必须实现 | 说明 |
|---|---|---|---|
| `name` | `str` 类属性 | 建议 | 显示在界面上的名字 |
| `choose_move` | `(state: State) -> str \| None` | ✅ | 返回 UCI 着法。返回 `None` 记为失败 |
| `game` | `Game` 属性 | — | 平台注入。层 2 用法通过它 `submit` |
| `color` | `"w"` / `"b"` 属性 | — | 平台注入 |
| `on_game_start` | `(state, color) -> None` | ❌ | 开局钩子 |
| `on_game_end` | `(result: str) -> None` | ❌ | 终局钩子 |
| `on_opponent_move` | `(move: str) -> None` | ❌ | 对手走完 |

---

## 7. `Client`（跨进程，方法名同构）

| 成员 | 对应 HTTP | 说明 |
|---|---|---|
| `Client(base_url, *, timeout=10)` | — | 如 `Client("http://127.0.0.1:8000")` |
| `.state()` | `GET /state` | 返回 `State` |
| `.board()` | `GET /state` | 返回 `Board` |
| `.submit(move)` | `POST /move` | 返回 `Result` |
| `.legal_moves()` | `GET /legal_moves` | |
| `.wait_my_turn(timeout)` | 轮询 `GET /state` | |
| `.reset(fen=None)` | `POST /reset` | |

服务端只需 3 个端点，`curl` 即可玩：

```bash
curl localhost:8000/state
curl -X POST localhost:8000/move -d '{"move":"e2e4"}'
curl -X POST localhost:8000/reset -d '{}'
```

---

## 8. 事件表（`game.on(...)`）

| 事件名 | 回调参数 | 触发时机 |
|---|---|---|
| `move` | `(move, result)` | 任何一方成功落子 |
| `illegal` | `(move, result)` | 落子被拒（含人类点错） |
| `opponent_move` | `(move)` | 对手成功落子 |
| `game_over` | `(result, reason)` | 终局 |
| `timeout` | `(side, seconds)` | 某方超时 |
| `retry` | `(side, attempt, result)` | 某方第 n 次被拒 |

---

## 9. 异常表

| 异常 | 何时抛 |
|---|---|
| `IllegalMoveError` | `submit(move, strict=True)` 且被拒；或 `state.apply()` 用了非法着法 |
| `NotYourTurnError` | `strict=True` 且不轮到你 |
| `GameOverError` | `strict=True` 且对局已结束 |
| `TimeoutError` | `wait_my_turn` 超时后的严格模式 |
| `AgentLoadError` | `agents/` 下的文件导入失败 / 找不到 `Agent` 子类 |
| `EngineError` | Stockfish 子进程启动失败或异常退出 |

> 默认 `strict=False`：**一律不抛，只返回码**。学生基本不会遇到异常。

---

## 10. 选手标识（`white=` / `black=` 的合法写法）

| 写法 | 含义 |
|---|---|
| `"human"` | 人类，等页面点击 |
| `"builtin:random"` | 内置随机 |
| `"builtin:greedy"` | 内置贪心 |
| `"builtin:minimax2"` | minimax 深度 2 |
| `"builtin:minimax3"` | minimax 深度 3 + alpha-beta |
| `"builtin:stockfish"` | Stockfish（ELO 与时限可配） |
| `"agents/my_agent.py"` | 按路径自动导入 |
| `"uci:名字"` | `agents/agents.json` 里 `type: "uci"` 的条目（见 §15） |
| `"http:名字"` | `agents/agents.json` 里 `type: "http"` 的条目（见 §15） |
| `MyAgent()` | 直接传实例（层 2 / 训练用） |

---

## 11. 工具函数与常量

| 名称 | 签名 | 说明 |
|---|---|---|
| `uci` | `uci(x1, y1, x2, y2, promo="") -> str` | 坐标转着法串 |
| `square` | `square(x, y) -> str` | `(4,1) -> "e2"` |
| `xy` | `xy(sq) -> tuple[int,int]` | `"e2" -> (4,1)` |
| `START_FEN` | 常量 | 初始局面 |
| `RC` | 常量类 | 返回码枚举 |
| `__version__` | `str` | |

---

## 12. CLI

| 命令 | 用途 |
|---|---|
| `python -m chessarena serve [--port 8000]` | 起网页 |
| `python -m chessarena play --white A --black B [--live]` | 命令行跑一局，打印 PGN |
| `python -m chessarena test agents/x.py --vs builtin:greedy --games 20` | 批量自测，输出胜率与用时 |
| `python -m chessarena league config.yaml` | 跑联赛，生成 `results/*.html` |
| `python -m chessarena replay results/x.pgn` | 终端回放 |

---

## 13. `config.yaml` 键

| 键 | 默认 | 说明 |
|---|---|---|
| `server.host` | `127.0.0.1` | |
| `server.port` | `8000` | |
| `game.timeout` | `3.0` | 每步总时长（含全部重试） |
| `game.max_retries` | `3` | 一步最多被拒几次 |
| `game.on_retry_exhausted` | `forfeit` | `forfeit` 判负 / `random` 替走一步 |
| `game.on_timeout` | `forfeit` | |
| `league.rounds` | `2` | |
| `league.openings` | `8` | 随机开局步数，防同质对局 |
| `league.max_concurrent` | `4` | 并发进程数 |
| `builtin` | `[random, greedy, minimax2, minimax3, stockfish]` | 启用哪些内置档 |

---

## 14. 三条硬保证

1. **原子性** — `submit` 返回非 0 时，局面 / 轮次 / 时钟 / 历史一样都不变。
2. **单写入口** — `Board` 无写方法；任何落子必经 `Game.submit()`。
3. **确定性** — 同 FEN + 同着法 ⇒ 同结果；`legal_moves` 顺序固定。

---

## 15. 外部对手注册（UCI 引擎 / HTTP 服务）

同进程的 Python `Agent` 之外，平台支持两种进程外对手。两者都只是"被裁判驱动的一方"：调用 `choose_move` 等价于问它要一步，落子仍然只走 `Game.submit()`。

### 15.1 `agents/agents.json`

```json
[
  {"name": "我的C++Bot", "type": "uci",  "cmd": ["./my_bot", "--threads", "1"], "timeout": 5.0,
   "options": {"Threads": 1, "UCI_LimitStrength": true, "UCI_Elo": 1600}},
  {"name": "云端神经网络", "type": "http", "url": "http://10.0.0.5:9000/move", "timeout": 10.0}
]
```

| 键 | 适用 | 必填 | 说明 |
|---|---|---|---|
| `name` | 全部 | ✅ | 与 `"uci:名字"` / `"http:名字"` 匹配；重复即报 `AgentLoadError` |
| `type` | 全部 | ✅ | `"uci"` / `"http"` |
| `cmd` | uci | ✅ | 字符串数组，**不经 shell**；相对路径以项目根为基准 |
| `url` | http | ✅ | 接收 `POST` 的完整地址 |
| `timeout` | 全部 | ❌ | 秒，默认 `5.0`(uci) / `10.0`(http)；不得超过 `game.timeout` |
| `options` | uci | ❌ | 启动后按 UCI 协议 `setoption` 下发 |

文件缺失或条目非法 ⇒ `AgentLoadError`；页面下拉框只显示加载成功的对手。

### 15.2 UCI 线协议（平台是 GUI 侧）

启动 `cmd` 后按序执行，每步一次问答；任何一步超时或进程退出 ⇒ 本步记 `EngineError`：

```
→ uci                     ← id name ... / id author ... / uciok
→ isready                 ← readyok
→ [setoption name <K> value <V>]      # 每个 options 一条
→ ucinewgame
→ position fen <FEN>                  # 不追加 moves，用完整 FEN
→ go movetime <剩余毫秒>
← bestmove <e2e4> [ponder <...>]      # 读一行即停；不解析 info
```

- `go movetime` 的毫秒数 = 剩余时钟预算 × 0.9，最少 50 ms。
- `bestmove 0000` 或 `bestmove (none)` ⇒ 视为 `None`（按"返回 None"判负，见 §5/§7）。
- 对局结束或 `Arena.close()` 时发 `quit`；5 秒不退则 kill 进程。
- Stockfish 即此协议的实例（L5），`UCI_Elo` 通过 `options` 配置。

### 15.3 HTTP 线协议

请求（`Content-Type: application/json`）：

```json
{"fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
 "turn": "w", "ply": 2, "history": ["e2e4", "e7e5"],
 "legal_moves": ["d2d4", "g1f3"]}
```

响应（`200`）：

```json
{"move": "g1f3"}
```

| 情况 | 平台处理 |
|---|---|
| `200` + 合法 `move` | 正常落子 |
| `200` + 不合法/格式化失败 `move` | 同 `-1` / `-2`，计入重试 |
| `200` + `{"move": null}` | 视为 `None`（判负） |
| `4xx` / `5xx` | 本步失败，计入重试；`reason` 取响应体前 200 字符 |
| 超时（`timeout`） | 计入 `timeout` 处置（§13） |

> **约定**：`turn` 用 `"w"`/`"b"`，与 `State.turn` 一致；`legal_moves` 与 `State.legal_moves` 同序同内容。两种协议都不改棋盘——平台只把它的回答转成 `submit()` 的一次调用。
