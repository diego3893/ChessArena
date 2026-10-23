# Project Context — ChessArena

> 耐久项目状态，用于上下文丢失后恢复。当前状态各节保持简短、原地更新。
> 最后更新：2026-10-23 01:30（全量复检：文档、媒体资源、依赖、阶段划分）

## 1. Mission

- **Final goal**：为大学研讨课提供一套单机国际象棋 AI 环境。学生自己写 AI（从 minimax 起步，可到强化学习），既能训练，也能对战观战。
- **Success criteria**：
  1. 单机网页 UI，可用且美观；
  2. 人机对战 + 机器 vs 机器对战（可观战）；
  3. 稳定的 AI API：读局面、枚举合法着法、落子；
  4. 内置多档 minimax AI，作为人机对手与学生的评测基线；
  5. 学生 AI 同一套代码既能无头训练，也能实时上屏对战；
  6. 一条命令跑完整联赛并给出 ELO。
- **Highest-priority metrics**：规则正确性 > API 稳定性 > UI 观感 > 复杂度。

## 2. Hard Constraints

- **单机运行**。明确不做联机对战、不做账号体系、不做数据库。
- **Windows** 环境下开发与使用（用户机器）。
- **前端零构建**：不安装 Node 依赖、不跑 pnpm/vite/esbuild 构建链。
- **棋盘只读**：唯一写入口是 `Game.submit()`；任何落子必须过裁判校验，非法落子不得改变任何状态（原子性）。
- **规则正确性交给库**（python-chess），不自己实现走法生成与胜负判定。
- 学生 AI 以 Python 为主，但必须允许任意语言经 UCI 或 HTTP 接入。
- **依赖最小集**（已全部装好，见 §15）：`chess`、`fastapi`、`uvicorn`、`pyyaml`、`websockets`。测试用标准库 `unittest`，不引入 pytest（D011）。

## 3. User Requirements

- R1 UI 可用，最好美观。
- R2 支持人机对战，以及两个机器对战。
- R3 提供给 AI 使用的 API：棋盘状态、落子函数等。
- R4 内置 AI（minimax 类搜索），用于人机对战，同时作为学生的参照基线。
- R5 学生的 AI **在训练和最终对战时都能直接操作棋盘**（同一套对象与方法），而非只在训练时可用。
- R6 **API 命名由实现方决定**，用户不指定签名；用户负责向学生解释调用约定。
- R7 **非法落子返回错误标志（如 -1），允许 AI 重新落子**，而不是直接判负。
- R8 用户当前只要求"棋盘这边"的设计与实现；UI/联赛可后置。
- R9 单机即可。

## 4. Current State

**Confirmed（2026-10-23 10:0x，阶段 5、6 完成，仅剩浏览器人工验收）：**

- **可运行**：`chessarena/` 34 个模块 + 前端 700 行；平台共 43 个 `.py` / 4,811 行（含 examples/assignments/tests）；`tests/` **100 个用例全绿**（Stockfish 引擎用例在沙箱内 skip）。
- **交付面**：`play` / `serve`（含模型下拉）/ `test`（自测）/ `league`（ELO+HTML）/ `replay`（终端回放）；五档 AI + 学生 `agents/` + `agents.json` 的外部 UCI/HTTP 对手。
- **内核**：五返回码 + 原子性 + 重试预算 + 硬超时 + 终局 + 事件 + PGN + `history_san`/`captured`；`TransientError`（外部对手可重试）。
- **服务**：`web/session.py`（驱动线程 + 广播 + 暂停/单步/调速/悔棋/认输/换人 + 心跳 + 自愈）、`web/server.py`（9 个 HTTP 端点 + `WS /ws` + 静态页）、`Client`、录像 JSONL。
- **前端**：`web/ui/*` 零构建；白方/黑方模型下拉（人类 / L1–L5 / `agents/*.py` / `uci:…` / `http:…`）+ 开局；落子/升变/记谱/吃子/悔棋/认输/翻转/导出 PGN/调速与暂停单步/自动校准。
- **联赛**：`chessarena/league.py` —— 单循环、随机开局、`max_concurrent` 多进程（=1 时本进程）、ELO（400 分制 K=32）、非法率、平均每步、HTML 报告 + 每局 PGN、断点续跑。
- **教学包**：`agents/examples/`（random / minimax αβ / HTTP client 三个样例）、`assignments/`（eval & minimax 骨架 + `grade.py`）、`config.yaml`、`start.bat`、`requirements.txt`、`README.md`。
- **L5 强度**：默认 `UCI_Elo=2600` + 每步 1.0s（`config.yaml` 的 `stockfish.elo/movetime` 或环境变量可调）。实测 2600 对 L4 **42 半步将杀**，2200 对随机 46 半步将杀。
- **实测**：联赛 random+greedy 2 局 0.1s、报告与 PGN 正常；`grade.py` 4 局 0.5s；100 用例 12.1s。
- **版本控制**：`a7da3df` → `8eeaab2` → `b4a56b5` → `3a5e2c9` → `661522a` → `4effeef` → `e6a70b0` → `2f3fc7f` → `4666e4e`；本轮（L5 调强）待提交。

**Current assessment：**

- 需求 R1–R9 全部有对应实现；只剩"真实浏览器里点一遍"这一项人工验收（P008）与"新机器三步启动"的实测。
- 教学链路完整：学生写 `agents/x.py` → 页面下拉即战 → `test` 量化 → `league` 排名。
- **当前位置：阶段 0–6 全部完成（M0–M6 代码层面），M3/M6 待人工验收。**

**Main issue：**

- 无阻塞项；可选后续：页面内回放（读 `runs/*.jsonl`）、联赛页面直播、变体棋种。


## 5. Architecture / Mental Model

```
浏览器 UI (chessground, 纯渲染)
        ↕ WebSocket / HTTP
裁判 Game  ←—— 唯一真相源，唯一写入口
        ↕ Agent 接口
AI（内置 minimax / 学生 Agent / UCI 引擎 / HTTP 服务）
```

- **裁判层唯一**。UI 与 AI 都只能"提出"着法，由裁判校验后广播。
- **人是另一种 Agent**：人机 = 一方是人类（等前端点击）；机机 = 两方都是程序。代码路径一致。
- **`Board` 只读**（无任何写方法），`State` 是不可变快照且带 `last_error`（上次被拒原因）。
- **着法格式唯一**：UCI 字符串（`e2e4`、`e7e8q`）。
- **返回码**：`0` OK / `-1` ILLEGAL_MOVE / `-2` BAD_FORMAT / `-3` NOT_YOUR_TURN / `-4` GAME_OVER。失败原子回滚。
- **重试**：`max_retries=3`；所有尝试**共享同一个每步 `timeout=3.0s`** 预算；用尽后 `forfeit`（课堂演示可切 `random`）。人类路径不消耗重试次数。
- **三种运行模式**：`live=True`（推送到页面）/ `live=False`（无头，每秒数千步）/ `record=True`（无头+录像）。方法名与校验逻辑完全一致。
- **三种接入位置**：同进程 `Agent` 子类（平台 import）/ UCI 子进程 / HTTP `Client`（3 个端点）。
- **内置五档**：L1 random、L2 greedy、L3 minimax 深度2、L4 minimax 深度3+alpha-beta、L5 Stockfish。L1–L4 每档独立文件、50–150 行，作为教材。
- **代码分层 ↔ 阶段**：内核（阶段 1）/ 服务与模式（阶段 2）/ 前端（阶段 3）/ 更强 AI（阶段 4）/ 联赛（阶段 5）/ 教学包（阶段 6）。

## 6. 工作方案阶段（Work Plan Phases）

**规则**：每个阶段以"可运行的出口条件（里程碑）"结束；阶段收尾时必须回到本文件更新状态与验证结论。跨阶段只允许 3 与 4 并行（都只依赖内核）。

| 阶段 | 目标 | 出口条件（里程碑） | 规模（粗估） | 状态 |
|---|---|---|---|---|
| **0 · 文档与资源冻结** | 4 份文档对同一接口只有一种说法；前端产物落到项目内 | **M0**：P003 的 9 处冲突改完；P005 的 UCI/HTTP 注册协议补进总表；`vendor/chessground/` 迁入；GPL 结论（P002）记录为决策 | S · 半天 | **完成**（M0 达成） |
| **1 · 裁判内核 + 命令行闭环** | `chessarena` 包最小纵向切片：`Game.submit` 全返回码、原子性、重试预算、超时、终局判定、PGN；内置 L1/L2 | **M1**：`python -m chessarena play --white builtin:random --black builtin:greedy` 跑完整局并打印 PGN；`unittest` 覆盖 5 个返回码 + 原子性 + 终局；中文不乱码 | M · 600–800 行 | **完成**（M1 达成，实测 1,450 行） |
| **2 · 运行模式 + Web 服务 + Client** | `live` / `headless` / `record` 三模式；FastAPI 3 端点 + WebSocket 推送；跨进程 `Client` 方法名同构 | **M2**：无头实测 ≥1000 plies/s；`curl` 三端点可用；`Client` 与同进程 API 同名同返回 | M | **完成**（M2 达成，吞吐 7,067 plies/s） |
| **3 · 前端（chessground 零构建）** | 引 vendor 的 `min.js` + CSS：合法点高亮、升变、上一步、将军、SAN 列表、吃子、悔棋、翻转、导出 PGN；人机 + 机机（调速/暂停/单步） | **M3**：浏览器人机对局可完成并正确判负；机机可观战；控制台零报错 | L | **实现完成，待人工浏览器验收**（E006） |
| **4 · 五档内置 + Stockfish** | L3 minimax2 / L4 minimax3+alpha-beta（各独立 50–150 行）；解压 Stockfish 走 UCI，配 ELO/时限 | **M4**：五档在 UI 中可选；实测每步耗时写入文档（L4 中局 ≤1s）；Stockfish 冒烟对局通过 | M | **完成**（M4 达成：L4 ≤0.86s，Stockfish 返回合法着法） |
| **5 · 联赛 + ELO + 报告** | 循环赛、随机开局、并发、ELO、**非法率列**、`results/league-*/index.html` + PGN 打包、断点续跑 | **M5**：一条命令跑循环赛并生成 ELO 表 | M | **完成**（M5 达成，E008） |
| **6 · 教学交付** | `agents/examples/` 3 个样例、`assignments/` 骨架 + 评分脚本、`requirements.txt`、`start.bat`、`config.yaml`、`README.md` | **M6**：新机器按 README 三步启动；3 个样例通过自测命令 | S–M | **代码完成**（新机器实测待用户，E009） |

**依赖**：0 → 1 → 2 → 3；4 依赖 1；5 依赖 2；6 最后。**里程碑 ↔ 需求**：M1↔R3、M2↔R5、M3↔R1/R2、M4↔R4、M5↔"一条命令出 ELO"、M6↔教学使用。

**当前阶段判定**：阶段 0–6 全部完成（M0–M2、M4、M5 达成；M3/M6 的"人工验收"待用户点一遍页面与在新机器上跑一次 `pip install -r requirements.txt && python -m chessarena serve`）。

## 7. Important Files

| File | Purpose | Notes |
|---|---|---|
| `docs/chessarena-API总表.md` | **接口单一事实来源**（§0–§16） | 实现照此写；与其他文档冲突时以它为准（D010） |
| `docs/chessarena-API规格.md` | 设计意图、返回码语义、重试规则 | 已与总表对齐 |
| `docs/chessarena-使用说明书.md` | 产品形态、界面线框、五档难度、教学节奏 | 已与总表对齐（P003 关闭） |
| `docs/chess-ai-platform-research.md` | GitHub 选型调研（星数/License 实测） | 调研期结论；其中"非法着法判负"已被 D004 取代 |
| `chessarena/core/game.py` | 裁判：`submit` 五返回码、原子性、重试/超时、终局、事件、PGN、`history_san`/`captured` | 阶段 1 核心，约 540 行 |
| `chessarena/core/state.py` | 不可变快照 + `apply` 沙盘推演 | 学生写 minimax 的入口 |
| `chessarena/core/board.py` | 只读棋盘视图（无写方法） | 与 `Game` 共享同一份真相 |
| `chessarena/core/{rc,result,moves,agent,arena,errors,recorder}.py` | 返回码 / 结果 / 坐标 / 选手 / 装配 / 异常 / 录像 | `record=True` 时写 `runs/<game_id>.jsonl` |
| `chessarena/core/external.py` | `agents.json` 注册表 + UCI 对手 + HTTP 对手 + `TransientError` 语义 | 协议见总表 §15 |
| `chessarena/web/session.py` | 服务端会话：驱动线程 + `Hub` 广播 + 暂停/单步/调速/悔棋/认输/换模式 | 单进程一局（D017） |
| `chessarena/web/server.py` | FastAPI：HTTP 端点 + `WS /ws` + 静态页（`/`、`/ui`、`/vendor`） | 协议见总表 §16 |
| `chessarena/web/ui/index.html` | 页面骨架（顶栏 / 棋盘 / 侧栏 / 控制 / 弹层） | 引 chessground 的 CSS 与 ESM |
| `chessarena/web/ui/app.js` | 连接 WS、渲染快照、落子/升变/悔棋/导出、机机调速 | **不含规则**，只信服务端 |
| `chessarena/web/ui/style.css` | 深色布局、面板、弹层、响应式 | 676 行前端合计 |
| `chessarena/client.py` | `Client`：stdlib urllib，方法与同进程同构 | 无第三方依赖 |
| `chessarena/builtin/evaluation.py` | 共用评估：子力 + 兵推进 + 极简位置项（约 55 行） | 学生改这里的价值表就能玩 |
| `chessarena/builtin/minimax2.py` | L3：negamax 深度 2（无剪枝，约 45 行） | 教材：递归骨架 |
| `chessarena/builtin/minimax3.py` | L4：αβ + MVV-LVA + 迭代加深（0.85s 预算，约 95 行） | 实测 ≤0.86s/步 |
| `chessarena/builtin/stockfish.py` | L5：`UCI_LimitStrength`/`UCI_Elo`，默认 **2600**、1.0s | `config.yaml` 的 `stockfish.*` 或 `CHESSARENA_STOCKFISH_ELO/_MOVETIME` 覆盖（环境变量优先） |
| `chessarena/engines/uci.py` | UCI 适配：`SimpleEngine` 启停、选项、`best_move(fen)`、统一 `EngineError` | 与总表 §15.2 同一协议 |
| `chessarena/league.py` | 循环赛编排、进程池并发、ELO、非法率、HTML 报告、断点续跑 | `max_concurrent=1` 时本进程执行（沙箱可测） |
| `chessarena/cli.py` | `play` / `serve` / `test` / `league` / `replay` | 全部可用 |
| `tests/test_kernel.py` | 32 个用例（返回码/原子性/终局/驱动） | `python -m unittest discover -s tests -t .` |
| `tests/test_server.py` | 19 个集成用例（真实 uvicorn + HTTP + WS + Client + 录像 + 静态资源） | 每例起随机端口的服务 |
| `tests/test_ui.py` | 4 个静态用例（选择器/资源/类名/无前端规则） | 挡住"JS 找不存在的 id"这类错 |
| `tests/test_league.py` | 6 个用例（ELO、编排、报告、续跑） | 报告含 ELO/非法率 |
| `tests/test_external.py` | 6 个用例（agents.json、HTTP 对手、扫描） | 本地 HTTPServer 模拟 |
| `tests/test_cli.py` | 7 个用例（play/league/test/replay/help） | 捕获 stdout |
| `tests/test_builtin.py` | 11 个用例（五档注册、Qxf7#、合法性、预算、Stockfish 冒烟） | 引擎用例在沙箱内 skip（P009） |
| `vendor/chessground/` | 前端预构建产物（min.js 33,291 B + 3 CSS + LICENSE） | 页面经 `/vendor/...` 直接引 |
| `thirdparty/stockfish/` | L5 引擎（已解压，Stockfish 19，103 MB exe） | 已 gitignore，按需重新解压 |
| `thirdparty/chessground/` | 参考源码（GPL-3.0，shallow clone v10.5.0） | 仅供阅读；**不需要构建**，无 `dist/`；已 gitignore |
| `agents/` | 学生 AI（一层 `*.py`）+ `agents.json` 外部对手 + `examples/` 三样例 | `Arena.agents()` 扫描 |
| `assignments/` | `eval_stub.py` / `minimax_stub.py` 骨架 + `grade.py` 自评 + README | 作业说明与评分口径 |
| `config.yaml` / `start.bat` / `requirements.txt` / `README.md` | 配置、Windows 一键启动、依赖、总览 | 阶段 6 |

`<old-ws>` = `C:\Users\30130\Documents\deepseek-harness\default-workspace`（旧暂存区；`vendor/` 已迁出，仅留归档）。

## 8. Decisions

### D001 — 选国际象棋，而非中国象棋

**Decision:** 第一版做国际象棋。
**Reason:** 规则库成熟度差距是数量级的；中国象棋没有"fork 即可用"的美观 Web 平台。
**Evidence:** 调研实测——python-chess 2892★ / GPL-3.0 且活跃；中国象棋高星项目为 Qt 桌面（XMuli 831★）或 Java 引擎加载器（public-Xiangqi 362★），唯一 Web 平台 pychess-variants 317★ 是 AGPL 大工程。
**Implication:** 架构中 Game 是插件，未来接中国象棋只换规则层 + 重画棋盘。
**Status:** Active

### D002 — 规则内核用 python-chess（`pip install chess`）

**Decision:** 不自己实现走法生成，直接依赖 python-chess。
**Reason:** 合法性、将死/逼和/三次重复/50 步、FEN/PGN、UCI 通信全部现成。
**Evidence:** 库自身文档与 API 覆盖全部需求；GPL-3.0（校内使用无所谓）；已装 1.11.2 并可 import。
**Implication:** 平台复杂度集中在校验层与 Agent 层，约 600–800 行。
**Status:** Active

### D003 — 唯一写入口 `Game.submit()`，不保留 `move()` 别名

**Decision:** 只暴露 `submit(move, *, strict=False) -> Result`；用户明确要求"统一为 submit"。
**Reason:** 两个名字等于两个概念，长期会混乱；`Board` 退回纯只读视图。
**Evidence:** 用户 2026-10-23 明确指示；文档中 `move(` 已改为 `submit(`。
**Implication:** 学生接口只有 `submit`；不要再引入同义方法（`place`/`commit` 亦已废弃）。
**Status:** Active

### D004 — 非法落子返回错误码并允许重试，而非直接判负

**Decision:** `-1` / `-2` 可重试，上限 3 次。
**Reason:** 学生代码必然有 bug；直接判负会让一节课被一个笔误毁掉。
**Evidence:** 用户明确要求"返回 -1 让 AI 重新落子"。
**Implication:** 必须配上限，否则死循环会卡死对局服务（见 D009）。
**Status:** Active

### D005 — 着法格式只用 UCI 字符串

**Decision:** `"e2e4"`、`"e7e8q"`；拒绝 SAN（`"Nf3"`）、拒绝 `drop(x, y, color)`。
**Reason:** SAN 有歧义；`drop(x,y,color)` 缺"来源格"与"棋子类型"信息。
**Evidence:** 用户表示"API 接口你来定义即可"。
**Implication:** 坐标版用工具函数 `uci(x1,y1,x2,y2,promo)`；不要新增坐标式 `submit` 重载。
**Status:** Active

### D006 — 前端用 chessground 的**官方预构建包**，不用源码构建

**Decision:** 直接 vendor `dist/chessground.min.js` + `assets/*.css`。
**Reason:** 源码构建要求 pnpm ≥12 与 POSIX shell，Windows 上跑不通；npm 包已自带构建产物。
**Evidence:** E001、F001。
**Implication:** 页面用 `<script type="module">` 直接引 `vendor/chessground/dist/chessground.min.js`，全程不装 Node 包。
**Status:** Active

### D007 — 前端零构建

**Decision:** 不引入 npm/pnpm/vite 构建步骤。
**Reason:** 用户 npm 未在 PATH 常态可用、pnpm 缺失；课堂项目不值得维护构建链。
**Evidence:** E002。
**Implication:** 所有前端资源以静态文件形式 vendor；改动只改静态文件。
**Status:** Active

### D008 — 不做联机对战

**Decision:** 单机；页面仅本机访问。
**Reason:** 用户明确"不做联机，单机即可"。
**Evidence:** 用户 2026-10-23 指示。
**Implication:** 不写 WebSocket 房间逻辑；但"落子推送"仍走本机 WebSocket 单连接。
**Status:** Active

### D009 — 重试共享同一步的时钟预算

**Decision:** 每步 `timeout=3.0s` 覆盖全部重试尝试。
**Reason:** 否则学生可用"故意被拒"换取额外思考时间，形成漏洞。
**Evidence:** 设计推演；无实测数据。
**Implication:** 裁判需在每次尝试前扣减剩余预算，而非每次重置。
**Status:** Active

### D010 — 文档冲突一律以《API总表》为准，《使用说明书》向总表修订

**Decision:** 总表是 SSOT；发现冲突时改说明书，不改总表。
**Reason:** 总表已与规格一致；说明书承载产品叙事，最容易漂移。
**Evidence:** P003 的 5 处冲突全部在说明书侧。
**Implication:** 新增/改名接口必须先落总表；说明书只能引用。
**Status:** Active

### D011 — 测试用标准库 `unittest`，不引入 pytest

**Decision:** `python -m unittest discover -s tests`。
**Reason:** 本机 pytest 未装；课堂环境依赖越少越好；断言型用例足够。
**Evidence:** E003 探测 `pytest=False`。
**Implication:** 不写 pytest fixture/conftest；需要临时目录用 `tempfile`。
**Status:** Active

### D012 — 所有中文输出强制 UTF-8

**Decision:** CLI 入口 `sys.stdout.reconfigure(encoding='utf-8')`；文件读写显式 `encoding='utf-8'`。
**Reason:** 本机 Python stdout 为 `gbk`，中文直接变乱码，`Result.reason` 与 PGN 注释都会中招。
**Evidence:** P004 实测。
**Implication:** 我在 pwsh 里验证中文前先 `$env:PYTHONIOENCODING='utf-8'`。
**Status:** Active

### D013 — 为 `ChessArena` 初始化 git，排除大文件

**Decision:** `git init` + 首次提交文档与上下文；`.gitignore` 排除 `thirdparty/*.zip`、`thirdparty/chessground/`、`runs/`、`results/`；`.gitattributes` 让 `vendor/**` 逐字节保真（`-text`），文本统一 LF。
**Reason:** 多阶段实现需要 diff / 回滚；vendor 的 min.js 不能被换行转换破坏哈希。
**Evidence:** E003（原先无任何仓库）；首次提交 `a7da3df` 后 `vendor` 哈希未变。
**Implication:** 每完成一个阶段做一次提交；`thirdparty/` 的大文件按需重新下载。
**Status:** Active

### D014 — 接受 chessground 的 GPL-3.0（用户已确认）

**Decision:** 前端用 chessground 预构建产物，接受 GPL-3.0-or-later 的传染性。
**Reason:** 校内教学 + 开源课程仓库合规；自写 SVG 棋盘要多花约 400 行且观感更差。
**Evidence:** 用户 2026-10-23 明确回答"可以接受"。
**Implication:** 页面分发时须同时提供源码（`thirdparty/chessground` 与上游地址已在 `vendor/chessground/README.md` 注明）。
**Status:** Active

### D015 — 快照与列表一律用不可变类型（tuple）

**Decision:** `State.board` 为 `tuple[tuple[str, ...], ...]`；`legal_moves` / `history` 为 `tuple[str, ...]`。
**Reason:** 与"只读快照"承诺一致，且可哈希（"顺序固定可用于哈希"才成立）；免去每次访问的防御性拷贝。
**Evidence:** 阶段 1 实现与 32 个测试；`np.array(state.board)` 仍可直接用。
**Implication:** 文档已同步 tuple 口径；学生拿到的不是 list，不能原地 `sort()`/`append()`——这本身是正确用法。
**Status:** Active

### D016 — 超时策略：内置档位内联，学生/外部走守护线程

**Decision:** `fast_local=True` 的 agent 直接内联执行（返回后测量耗时）；其余 agent 放进 daemon 线程并 `join(预算)`，超时就判负、线程弃置。
**Reason:** 内置档位不会卡死，内联可省每步线程开销（无头吞吐目标 ≥1000 plies/s）；学生代码可能死循环，必须能硬超时。
**Evidence:** E004 的无头吞吐实测（3,500+ plies/s）与超时用例。
**Implication:** 被弃置的线程若事后调用 `submit`，会因轮次/代数检查被拒；不要在 agent 里依赖线程局部状态。
**Status:** Active

### D017 — 传输层：单进程一局 + 单一快照形状 + HTTP 状态码映射

**Decision:** 一个服务进程只跑一局；所有消息里的 `state` 一律是 `Game.to_json()`；HTTP 状态码 `0→200 / -1,-2→400 / -3→409 / -4→410`，响应体始终带 `result` 与 `state`。
**Reason:** 单机课堂只有一个用户，多局/房间会引入不必要的会话概念（D008）；快照只一种形状，前端与 `Client` 不会各写一套解析。
**Evidence:** 总表 §16 定稿 + `tests/test_server.py` 14 个集成用例。
**Implication:** 想同时看多局就多开进程（不同端口）；任何新端点必须复用同一快照。
**Status:** Active

### D018 — AI 回合由服务端驱动线程推进，人类回合只等 HTTP

**Decision:** `Session` 起一个 daemon 驱动线程：轮到 AI 就按 `speed` 走，轮人类就空转；`POST /move` 在 AI 回合返回 `-3`；暂停/单步/调速经 `POST /control`。
**Reason:** 裁判层不该知道 HTTP；页面只要"看"，落子路径仍只走 `submit()`。这样机机观战、人机、暂停单步共用一条驱动逻辑。
**Evidence:** 集成测试 `test_control_pause_step_resume`、`test_move_when_ai_turn_is_409`。
**Implication:** 一个进程内只有驱动线程会推进 AI，别在别处再调 `game.step()`（会撞轮次）。
**Status:** Active

### D019 — 前端不含棋规：记谱/吃子/合法性全部由服务端算

**Decision:** 页面只做三件事——画 `state.fen`、发 `POST /move`、按 WS 消息刷新；SAN（`history_san`）与吃子（`captured`）由 `Game.to_json()` 提供；升变四选一在前端做，但只在服务端 `legal_moves` 里出现 5 字符着法时才弹。
**Reason:** 在 JS 里重写 SAN/吃过路兵/升变必然与 Python 侧漂移；页面与 PGN 必须永远一致。
**Evidence:** `test_ui.py::test_no_legacy_engine_calls`（前端不引 chess.js、不自己算合法着法）；`history_san`/`captured` 的内核测试。
**Implication:** 新增任何展示字段，先加到 `Game.to_json()`（并同步 §16.1），前端只读。
**Status:** Active

### D020 — 非法落子用"整盘重绘"回滚

**Decision:** 用户在页面上走了非法着法时，不手工把棋子挪回去，而是用服务端返回的 `state.fen` 重新 `ground.set()`。
**Reason:** 手工撤销要复刻 chessground 内部坐标与动画，容易和"最后一手/将军"标记不一致；重绘只有一个真相。
**Evidence:** `app.js::render` + `/move` 的 400 响应体带完整 `state`。
**Implication:** 代价是一次 180ms 动画重放，可接受；不要在前端维护第二份局面。
**Status:** Active

### D021 — L4 用"迭代加深 + 0.85s 预算"，而不是固定深度

**Decision:** `Minimax3Agent(budget=0.85, max_depth=4)`：逐层加深，超预算就停在上一层，返回最后一次完整搜索的最佳着法。
**Reason:** 固定深度 3 在开局较慢、在残局又浪费；预算制能同时满足"每步 ≤1s"和"能搜多深搜多深"。
**Evidence:** E007 实测 0.14–0.86s/步；`test_l4_respects_budget` 用 0.25s 预算验证不超时。
**Implication:** 改预算就改这一个参数；不要把深度硬编码回 3。
**Status:** Active

### D022 — UCI 接入交给 python-chess，而不是自己写协议栈

**Decision:** `chessarena/engines/uci.py` 用 `chess.engine.SimpleEngine` 管理 Stockfish 进程；对外仍暴露 `best_move(fen)` 与统一 `EngineError`。
**Reason:** UCI 握手、就绪、选项、超时、退出都是库的既有能力（D002 的同一逻辑）；自己写只会引入边界 bug。
**Evidence:** E007：`bestmove g1f3`（含启动 0.59s），复用进程第二次查询 0.2s。
**Implication:** 学生自写的 UCI 引擎（总表 §15.2）后续也走这个适配器；不要绕过它直接 `subprocess`。
**Status:** Active

### D023 — 联赛用进程池，`max_concurrent=1` 时退回本进程

**Decision:** `League.run` 在 `max_concurrent > 1` 时用 `ProcessPoolExecutor` 跑 `play_game(job)`；`=1` 时循环调用同一函数。
**Reason:** 纯 Python 搜索受 GIL 限制，线程并发没用；而进程池在沙箱/受限环境里起不来，需要一个可测的单进程路径。
**Evidence:** E008：2 局联赛 0.1s、报告与 PGN 正常；97 用例全绿（并发路径只在用户机器上跑）。
**Implication:** `play_game` 必须是模块级、参数可 pickle；不要在 League 里直接持有 Agent 实例。
**Status:** Active

### D024 — 外部对手的错误分两类：`EngineError`（判负）与 `TransientError`（计入重试）

**Decision:** UCI 启动失败抛 `EngineError`（一步判负）；引擎中途退出、HTTP 4xx/5xx、网络错误抛 `TransientError`，裁判按"这一步失败"计入重试预算，用尽才处置。
**Reason:** 总表 §15.3 要求 4xx/5xx 计入重试；而"引擎根本没起来"是配置错误，重试也不会好。
**Evidence:** `tests/test_external.py`（HTTP 500 → `TransientError`）；`Game._play_turn` 的 Transient 分支。
**Implication:** 新写外部适配器时，把"可重试"和"配置错"分开抛；不要把网络异常伪装成返回值。
**Status:** Active

### D025 — L5 默认 `UCI_Elo=2600`、1.0s，配置优先级 环境变量 > config > 默认

**Decision:** `StockfishAgent` 默认 2600 / 1.0s；`config.yaml` 增加 `stockfish.{elo,movetime,path}`；环境变量 `CHESSARENA_STOCKFISH_{ELO,MOVETIME}` 与 `CHESSARENA_STOCKFISH` 覆盖配置。
**Reason:** 1600 档会被随机棋手拖成三次重复和棋（E010）；课堂需要一个"认真下打不过"的档，同时保留按班调档的旋钮。
**Evidence:** E010 —— 2600 对 L4 42 半步将杀；2200 对随机 46 半步将杀；`test_arena_passes_config` / `test_env_overrides_config`。
**Implication:** 想温柔一点就把 `stockfish.elo` 调到 1600–1800；不要在代码里硬编码强度。
**Status:** Active

## 9. Experiments / Results

### E001 — chessground 预构建产物可得性与完整性

**Purpose:** 验证能否绕开 pnpm 与编译，直接拿到可用前端产物。
**Setup:** `npm pack @lichess-org/chessground`（缓存重定向到暂存区）。
**Result:** `lichess-org-chessground-10.5.0.tgz` 119,659 B；内含 `dist/chessground.min.js`（33,291 B）、3 套 `assets/*.css`（base 3,537 / brown 2,908 / cburnett 11,548 B）、LICENSE 35,147 B。校验：含 `export {` 与 `Chessground`，**无 `sourceMappingURL`**。
**Conclusion:** 可零构建使用；不需要 pnpm，不需要编译。

### E002 — 本机环境探测（首轮）

**Purpose:** 确认构建所需运行时是否就位。
**Result:** Python 3.12.5；pip 26.2.1；git 可用；node v24.16.0；**pnpm 不在 PATH**；`chess` / `fastapi` 当时均未安装。
**Conclusion:** 只差 pip 包；Node 侧不足以为 chessground 建构建链。

### E003 — 环境与仓库复检（2026-10-23 01:2x）

**Purpose:** 在开始写代码前核对依赖、版本、仓库状态与编码，替换过期记录。
**Result:**
- 依赖已装并可 import：`chess 1.11.2` / `fastapi 0.159.1` / `uvicorn 0.54.0` / `PyYAML 6.0.3` / `starlette 1.9.0` / `websockets` 存在；`pytest=False`、`httpx=False`。
- `thirdparty/chessground`：`git rev-parse` → `b4f6050`/`master`，`is-shallow-repository=true`，`package.json` 版本 10.5.0、`GPL-3.0-or-later`；`dist/` **不存在**。
- Stockfish zip：81,431,614 B；SHA256 `3C8BF1F9EA66A09350A40DF4F632288285AC206D99F33AB5842C408FC30B48A7`；含 `stockfish/stockfish-windows-x86-64-universal.exe` 103,046,300 B。
- 全项目 `.py` 文件数 = **0**。
- `workstation` 与 `ChessArena` **均无 git 仓库**（`fatal: not a git repository`）。
- `sys.stdout.encoding == 'gbk'`，中文 `print` 乱码；`PYTHONIOENCODING=utf-8` 后正常。
**Conclusion:** 依赖与素材齐备，可以开写内核；同时纠正三条过期上下文（项目根写权限、父目录 git、文档"已完全一致"）。

### E004 — 阶段 1 内核验收（M1）

**Purpose:** 验证 `Game.submit` 的五返回码、原子性、终局、重试/超时在真实棋例下成立，并测无头吞吐。
**Setup:** `python -m unittest discover -s tests -t .`（32 用例）；`python -m chessarena play` 跑随机/贪心对局。
**Result:**
- 32 个用例全绿，0.26 s（返回码 -1/-2/-3/-4、原子性、将杀/逼和/子力不足/50 步/三次重复、重试预算、超时、异常、弃权、层 2 自落子、事件、PGN 往返）。
- `random vs greedy`：106 半步逼和，0.03 s；`greedy vs random`：95 半步逼和 → **≈3,500 plies/s**（目标 ≥1000）。
- 同 `seed` 两次运行的着法序列完全一致（仅 `GameId`/`Date` 头不同）。
- 代码量：内核 15 个模块 1,450 行（不含 330 行测试）。
**Conclusion:** M1 达成；API 手感与文档一致，可直接作为阶段 2 的地基。

### E005 — 阶段 2 服务层验收（M2）

**Purpose:** 验证 HTTP/WS/Client/录像在真实 uvicorn 下成立，并复测无头吞吐。
**Setup:** `python -m unittest tests.test_server`（14 个用例，每个在后台线程起一个随机端口的 uvicorn）；手动 `python -m chessarena serve --port 8765` + urllib/`websockets.sync` 验证；吞吐用 200 步循环计时。
**Result:**
- 全部 46 个用例（32 内核 + 14 集成）全绿，4.8 s（阶段 3 又加了 4 个前端静态用例，现共 55）。
- `GET /state` → `turn=w`、20 个合法着法；`POST /move e2e4` → `200` + `ply=1`，AI 随即应手；非法着法 → `400`、格式错 → `400`、AI 回合 → `409`、终局后 → `410`。
- `POST /control`：`pause` 后 0.5 s 内 `ply` 不变；`step` 恰好 +1；`resume` 继续；`speed` 生效；未知动作 → `400`。
- WS：连接即收 `hello`，落子收 `move`，将杀收 `game_over`（`0-1`/`checkmate`），`ping`/`pong` 正常。
- `Client`：`state/legal_moves/submit/reset/wait_my_turn` 与同进程同码同因；`Client.submit("e2e5") == -1`。
- 录像：`record=True` 写 `runs/<game_id>.jsonl`，`move` 行数 == `ply`，终局追加 `game_over`。
- 无头吞吐 **7,067 plies/s**（200 步 / 0.015 s）。
**Conclusion:** M2 达成；前端现在只需消费 §16 的 `state` 形状。

### E006 — 阶段 3 前端实现与可自动化的验证

**Purpose:** 确认页面接线正确、资源可达，并划定哪些能在无浏览器环境验证。
**Setup:** `python -m unittest discover -s tests -t .`（55 用例）；`python -m chessarena serve --port 8766` + urllib 取 `/`、`/ui/*`、`/vendor/*`、`/state`；`websockets.sync` 收 hello；`Copy-Item app.js runs/app_check.mjs; node --check`。
**Result:**
- 55 个用例全绿（32 内核 + 19 服务 + 4 前端静态），6.2 s；连续跑 5 轮均绿。
- `/` → `200 text/html`（3,484 B）；`/ui/app.js` 11,694 B；`/ui/style.css` 6,402 B；`/vendor/...min.js` 33,291 B；`/vendor/...cburnett.css` 11,548 B —— 全部 `200`。
- `/state` 含 `human={w:true,b:false}`、`paused`、`speed`、`timeout`、`history_san`、`captured`；WS `hello` 带 `version`。
- `node --check app.js` 通过（ESM 语法无误）。
- 静态用例确认：`app.js` 引用的 13 个 id 全在 HTML 中；HTML 的 4 个 `/ui|/vendor` 资源都存在；HTML 类名都有 CSS 定义。
- **失败**：本机 Edge 在沙箱内无法启动（`--version` 都无输出、exit 空/`0x80000003`），`--headless --dump-dom` 拿不到 DOM → 真实点击/动画无法自动验收。
**Conclusion:** M3 的代码与接线已由测试覆盖，**浏览器人工验收仍待做**（P008）；这不阻塞阶段 4。

### E007 — 阶段 4 五档验收（M4）

**Purpose:** 确认 L3/L4 能在时限内选出合法且像样的着法，Stockfish 能经 UCI 接入。
**Setup:** `tests/test_builtin.py`（11 用例）；三个局面（开局 / 中局 / Qxf7# 杀局）逐个测；`play --white builtin:minimax3 --black builtin:minimax2 --max-plies 40`；Stockfish 用 PowerShell 管道与 `UCIEngine` 各验一次。
**Result:**
- 五档注册成功，`Arena.builtins()` 返回 `["random","greedy","minimax2","minimax3","stockfish"]`。
- L3：0.015–0.03s/步；L4：0.14–0.86s/步（预算 0.85s），开局选 `e2e4`、杀局找到 `f3f7`（Qxf7#）。
- L4 vs L3 跑 40 半步 10.0s，无被拒着法。
- Stockfish 19：`UCI_Elo` 支持 1320–3190；管道 `bestmove d2d3`；`UCIEngine.best_move` 返回 `g1f3`（0.59s 含启动），第二个 FEN 返回 `f1c4`（复用进程）。
- 全套 66 用例全绿（3 轮）；Stockfish 引擎用例在**沙箱内 skip**（P009）。
**Conclusion:** M4 达成；五档可直接进联赛评分。

### E008 — 阶段 5 联赛验收（M5）

**Purpose:** 验证编排、ELO、报告、续跑与并发路径。
**Setup:** `python -m chessarena league --players random,greedy --rounds 1 --openings 2 --concurrent 1 --max-plies 120 --out runs/league-smoke`；`tests/test_league.py` 6 个用例。
**Result:**
- 2 局 0.1s 完成，终端逐局打印；`runs/league-smoke/index.html` 含 ELO 表（两人均 1500，两和）与非法率、平均每步；`pgn/` 下 2 个 PGN。
- 续跑：重复执行后 `games.jsonl` 行数不变（不重复跑）。
- 编排：`rounds=2`、2 人 → 4 局，黑白各半。
- 3 人演示（random/greedy/minimax2，rounds=1，openings=4）：6 局 7.4s，ELO `minimax2 1531 > greedy 1498 > random 1471`，非法率全 0，报告落在 `results/demo-league/`。
- 边界：一局 200 步未终局时记为 `unfinished`（按 0.5 计），报告里原因可见——所以联赛默认 `max_plies=600`。
**Conclusion:** M5 达成；联赛可直接用于课堂排名。

### E009 — 阶段 6 教学包与 CLI 验收

**Purpose:** 确认"新机器按 README 三步启动"所需文件齐全，三条新命令可用。
**Setup:** `python -m unittest tests.test_cli tests.test_external`；`python assignments/grade.py agents/examples/random_agent.py --games 2`。
**Result:**
- `grade.py`：4 局 0.5s，输出对手得分率/非法率/用时，并写 `runs/grade-random_agent.json`。
- `test` 命令输出"胜率 / 平均每步 / 最长"；`replay` 打印记谱与结果，缺文件返回 2。
- `agents/examples/` 三个样例可被 `Arena.agents()` 之外的路径加载（`test` 命令）；
- `agents.json` 校验：缺 `cmd`/未知 `type`/重名一律 `AgentLoadError`；HTTP 对手用本地 HTTPServer 测通。
- 文件齐备：`config.yaml`、`start.bat`、`requirements.txt`、`README.md`、`assignments/*`。
- **未验证**：真·新机器上 `pip install -r requirements.txt` 的联网过程。
**Conclusion:** M6 代码层面完成，只剩用户的实机试用。

### E010 — L5 强度调档（用户要求"调强一点"）

**Purpose:** 1600 档会被随机棋手拖成三次重复和棋（用户实测），确认更合适的默认强度。
**Setup:** `random vs Stockfish(2200, 1.0s)`、`minimax3 vs Stockfish(2200/2600, 1.0s)`；`config.yaml` 的 `stockfish:` 段经 `Arena` → `make_builtin` 生效。
**Result:**
- 2200 vs random：**46 半步将杀**，21.5s（不再出现重复和棋）。
- 2200 vs L4：40 半步时子力 `21:23`（+2，未分胜负）——不够"打不过"。
- 2600 vs L4：**42 半步将杀**，决定性。
- 新增配置链：`config.yaml` 的 `stockfish.elo/movetime/path` 生效；环境变量 `CHESSARENA_STOCKFISH_*` 优先。
**Conclusion:** 默认改为 **2600 / 1.0s**（`UCI_Elo` 仍可在 1320–3190 间调）；单步含启动约 1.3s，仍在 3s 限时内。

## 10. Failed Attempts / Things Not To Repeat

### F001 — 在 chessground 源码克隆里用 npm 安装并构建

**Tried:** 在 clone 内执行 npm 安装（期望得到可用前端产物）。
**Result:** 报错（用户描述为"被进程占用"）；`node_modules` 未生成。
**Why it failed:** 该仓库声明 `packageManager: pnpm@12.9.0` 与 `engines.pnpm>=12`；`prepare` 脚本 `$npm_execpath run compile` 是 POSIX 语法，Windows cmd 不展开；npm 在 Windows 整理 `node_modules` 常见 `EBUSY`/`EPERM`。
**Retry only if:** 改用 pnpm ≥12 并接受 TypeScript 构建链（不建议，已有 D006 替代路径）。

### F002 — 用"关键词 grep"证明文档一致性（方法论失败）

**Tried:** 用 `别名` / `game.move` / `drop(` 三个词扫文档，得出"已完全一致"。
**Result:** 漏掉了 `place()`/`commit()`、`state.turn == "white"`、判定规则表"非法即判负"等多处旧设计，以及规格里 3 处取值域/事件名差异（P003 共 9 处）。
**Why it failed:** 校验口径来自"已知的旧 API 名"，而漂移发生在未列出的概念上。
**Do instead:** 以总表的**接口清单**为基准做逐条对账（对象、方法名、取值域、判定规则），而不是扫关键词。

### F003 — 按旧版 python-chess 的 API 名写终局检测

**Tried:** `board.is_threefold_repetition()`。
**Result:** `AttributeError`——本机 `chess 1.11.2` 里没有这个名字（改名/移除）。
**Why it failed:** 记忆中的 API 来自更老的版本，没有对当前安装版本核对。
**Do instead:** 1.11.x 用 `board.is_repetition(3)`（三次及以上）与 `board.is_fivefold_repetition()`；动手前用 `python -c "import chess; print([n for n in dir(chess.Board) if ...])"` 核对。

## 11. Bugs / Open Problems

### P001 — 删除 `ChessArena/chessground` 时 Windows 报"文件夹正在使用"

**Status:** **Resolved（失效）**。用户已把克隆移入 `thirdparty/chessground/` 且可正常读取/枚举，不再需要删除该目录。
**Keep for history:** 无 `.lock`、`git rev-parse` 正常，当时最可疑的是终端工作目录停留在内部。若将来再次出现，先关窗口/资源管理器再删。

### P002 — chessground 为 GPL-3.0，授权尚未确认

**Status:** **Resolved**（用户 2026-10-23 接受，见 D014）。vendor 目录内已附 LICENSE 与来源说明，满足"提供源码"要求。
**Keep for history:** 若将来需要闭源分发，改为自写 SVG 棋盘（约 400 行）是唯一干净路线。

### P003 — 文档内部冲突 9 处（说明书 6 / 规格 3），需按 D010 收敛

**Status:** **Resolved**（2026-10-23 已全部改写；`place(`/`commit(`/`"white"`/`409`/`on_opponent_move(`/`arena.game` 在 docs 里零残留）。实现后另同步了 tuple 类型口径（D015）与 `over_reason` 的 `forfeit`/`error` 取值。

**原始清单（留档，便于追溯）：**
1. 说明书 L193：`state.turn` 写作 `"white"`/`"black"`。
2. 说明书 L229–230：`board = game.board` 注释为"可逐格读写"。
3. 说明书 L310：`place()` / `commit()`。
4. 说明书 L318：判定表"非法即判负"（与 D004 冲突）。
5. 说明书 L397：`move` / `drop` / `place` 列表。
6. 说明书 L308：`IllegalMoveError` / 409。
7. 规格 L115：`over_reason` 取值集不一致。
8. 规格 L119：`on_opponent_move(callback)`。
9. 规格 L127：`piece_at` 返回 `None`。

### P004 — 本机 Python stdout 为 gbk，中文输出乱码

**Symptoms:** `print("中文测试")` → 乱码；`sys.stdout.encoding == 'gbk'`。
**Fix:** D012（CLI 入口已 `reconfigure(utf-8)`；文件一律 `encoding='utf-8'`）。我在 pwsh 验证前加 `$env:PYTHONIOENCODING='utf-8'`。
**Status:** Mitigated（有确定绕法，但每个新入口都要记得加）。

### P005 — 总表缺"UCI/HTTP 外部对手注册"协议

**Status:** **Resolved**（总表新增 §15：`agents.json` 字段、UCI 握手序列、HTTP 请求/响应 JSON；§10 增加 `"uci:名字"` / `"http:名字"`；说明书 §三 已引用）。阶段 2/4 实现时照 §15 写。

### P006 — 人类路径的"不消耗重试"需要显式标记

**Symptoms:** `HumanAgent` 走的是同一套 `_play_turn` 重试循环；若不区分，人类手滑也会在 `max_retries` 次后判负，违反《说明书》§四的承诺。
**Fix:** `Agent.is_human = True`（`HumanAgent` 已设）；裁判对这类 agent 只受时钟限制、不计重试。
**Validation:** `test_human_rejections_do_not_consume_retries`（两次非法后仍能落子，`ply == 1`）。

### P007 — 服务端 `reset/new` 不切换录像文件（已知限制）

**Symptoms:** `record=True` 时一局一个 `runs/<game_id>.jsonl`；`Session.control("new")` 会开新局，但录像仍写在与 `Arena` 关联的第一个 `game_id` 上（当前实现只在 `arena.new_game` 时挂 recorder）。
**Impact:** 只在"服务端跑录像"场景出现；无头 `record=True` 不受影响。
**Fix（阶段 3 一并做）:** `Session` 在 `new` 时新建 `Recorder`，旧文件补一条 `{"type":"aborted"}` 收尾。

### P008 — M3 缺浏览器人工验收；本机 Edge 在沙箱内无法启动

**Symptoms:** `msedge.exe --version` 无输出、退出码为空；`--headless=new --dump-dom` 产出 0 字节（`0x80000003`）。因此"点击/拖拽/动画/控制台零报错"无法自动验证。
**Known facts:** HTTP 资源全部 200、`node --check app.js` 通过、选择器/资源/类名静态对账通过（E006）；协议层由 19 个集成用例覆盖。
**Fix:** 由用户在本机浏览器打开 `http://127.0.0.1:8000/` 实测；把结果记入 §14 后再关闭本项。
**附带发现:** 55 用例里出现过 2 次时序性失败（均与"AI 抢先应手"有关）：`test_move_when_ai_turn_is_409` 改为先 `pause` 再提交；`test_snapshot_has_ui_fields` 改用 human-vs-human。之后连续 6 轮全绿。

### P009 — 沙箱内无法启动 Stockfish（子进程管道被禁）

**Symptoms:** `python-chess` 的 `popen_uci` 抛 `PermissionError(13, '拒绝访问', None, 5)`；同一 exe 用 PowerShell 管道（`"uci`n...`ngo movetime 300" | stockfish.exe`）正常返回 `bestmove`。即：**二进制没问题，是 workspace-write 沙箱禁止创建管道**。
**Known facts:** 一次 `danger-full-access` 单命令验证通过：`UCIEngine.best_move` → `g1f3`（0.59s），第二次 → `f1c4`。
**Impact:** 只有"引擎相关自动化"受影响：`test_engine_returns_legal_move` 在沙箱内 `skipTest`；网页与 `play` 用 L1–L4 不受影响。用户在自己终端（无沙箱）跑 L5 正常。
**Fix/Workaround:** 需要引擎验证时用 `danger-full-access` 跑单条命令；或由用户在本机执行 `python -m chessarena play --black builtin:stockfish`。

### P010 — 页面"卡住"：轮到黑方但 AI 不动（用户实测，2026-10-23）

**Symptoms:** 用户截图：1.d4 f5 2.f4 之后状态停在"黑方走棋 · 第 3 步"，棋盘与记谱都不再变化，右上角仍显示"已连接"。
**Reconciliation:** 自测无法复现——服务端每步都推进、WS 每条 move 都送达（人工对局 10 步收 10 条 move 消息）。因此判断为**客户端漏掉/未渲染某条推送后没有兜底**，或驱动线程异常无人知晓；页面并非"服务端真的停住"。
**Root cause:** 未复现；但暴露了三个真实缺陷：
1. 客户端没有任何状态校准：漏一条 `move` 就永久停在旧局面，且旧局面下不能落子（轮 AI）→ 表现为"卡死"。
2. 驱动线程 `_drive` 没有 `try/except`：任何异常都会让它**静默退出**，之后 AI 永不走。`game.step()` 不推进时还会以 0.35s 间隔空转。
3. 没有任何诊断入口，用户看不到"AI 在算 / 已死"。

**Fix（防御性，已实现）:**
- 服务端：WS 每 3s 推 `heartbeat`（完整快照）；`_drive` 包 `try/except` 并把异常打到 stderr；空转检测（`stalls`）；每 2s `ensure_driver()` 自动重启死掉的驱动；新增 `GET /debug`（`driver_alive`/`steps`/`stalls`/`last_error`/`clients`）。
- 客户端：所有网络快照走 `applyState()`（丢弃同局 `ply` 更小的旧快照）；5s 无消息即用 `GET /state` 校准；WS 重连去重；`render` 包 `try/catch`；AI 回合显示"思考中…"。
**Validation:** `tests/test_server.py::TestResilience` 4 个用例（heartbeat、驱动重启、空转检测、/debug）；全套 70 用例 3 轮全绿。
**Todo for user:** 复现时看服务器终端是否有 `[chessarena]` 行、浏览器 F12 控制台；若再次卡住，用 `GET /debug` 的 `stalls`/`last_error` 定位。

## 12. Current Working Set

- **Files currently being changed:** 无（阶段 5、6 已收尾，本轮待提交）。
- **Functions/components in focus:** 收尾验收：页面人工点一遍（模型下拉 / 人机 / 机机 / 升变）、新机器三步启动。
- **Immediate issue:** 无阻塞项；仅剩人工验收与"可选后续"。
- **Current hypothesis:** 联赛在课堂机器上默认 L1–L3 即可（L4 每步 0.85s，20 局 × 100 步 ≈ 30 分钟/对，需 `--players` 里避开）。
- **Next check:** 用户实机：`start.bat` → 页面选人机/机机；`python -m chessarena league --players random,greedy,minimax2` 跑一次小联赛。

## 13. Next Actions

**阶段 0–4：全部完成（M0–M2、M4）**
- [x] 文档口径、vendor、git、内核 + L1/L2/CLI（M1）
- [x] HTTP/WS/Client/录像（M2）
- [x] 页面 + 模型下拉 + 自愈（M3 代码）
- [x] 五档 + Stockfish UCI（M4）

**阶段 5（完成，M5）**
- [x] `chessarena/league.py`：编排、随机开局、进程池（=1 本进程）、ELO（400/K=32）、非法率、平均每步。
- [x] 报告：`results/league-*/index.html`（ELO 表 + 每局明细 + PGN 链接）+ `ratings.json` + `games.jsonl`。
- [x] 断点续跑（重跑跳过已完成局）。
- [x] CLI：`python -m chessarena league --players … --rounds … --concurrent …`。
- [x] **M5**：random+greedy 2 局 0.1s，报告/PGN 正常（E008）。

**阶段 6（完成，M6 实机待验）**
- [x] `agents/examples/`：`random_agent.py`、`minimax_agent.py`（αβ 深度3，只用 State API）、`http_client_agent.py`。
- [x] `agents/agents.json` 注册表 + UCI/HTTP 对手（`core/external.py`）；下拉框自动出现。
- [x] `assignments/`：`eval_stub.py`、`minimax_stub.py`、`grade.py`、`README.md`（作业与评分口径）。
- [x] `config.yaml`、`start.bat`、`requirements.txt`、`README.md`。
- [x] CLI `test`（胜率/每步耗时/最长）与 `replay`（`--board`/`--delay`）。
- [ ] **M6 实机验收**：用户在新机器上 `pip install -r requirements.txt` → `python -m chessarena serve`。

**可选后续（不在当前范围）**
- [ ] 页面内回放（读 `runs/<game_id>.jsonl`）。
- [ ] 联赛在页面里直播进度。
- [ ] 变体棋种（中国象棋只换规则层）。

## 14. Validation Status

- [x] **文档存在且可读**：`docs/` 4 份齐全（2026-10-23）。
- [x] **依赖可 import**：chess / fastapi / uvicorn / yaml / websockets（E003）。
- [x] **chessground 产物完整性**：含 `export {` 与 `Chessground`，无 sourcemap 引用；已迁入 `vendor/` 且哈希一致（`CCC1AAF…0A591`）。
- [x] **Stockfish 包可读**：zip 完整解出目录树；现已解压到 `thirdparty/stockfish/`（Stockfish 19），PowerShell 管道与 `UCIEngine` 均返回合法 `bestmove`。
- [x] **文档零冲突**：P003/P005 关闭；`docs/` 内 `place(`/`commit(`/`"white"`/`409`/`on_opponent_move(` 零命中。
- [x] 规则内核实现与单元测试：32 用例全绿（E004）。
- [x] 端到端：命令行一局输出 PGN（M1）。
- [x] HTTP 端点 + `Client` 同构（M2，19 个集成用例，E005）。
- [x] WebSocket 广播、暂停/单步/调速/悔棋/认输/换模式、录像 JSONL。
- [x] 静态页与资源 200、JS 语法通过、选择器/资源/类名对账（E006，4 个前端静态用例）。
- [x] 五档内置：L3/L4 合法且找到一步杀；L4 ≤0.86s；Stockfish 经 UCI 可用（E007，11 个用例）。
- [x] 联赛一条命令出 ELO + 报告（M5，E008，6 个用例）。
- [x] 学生 agents 扫描、`agents.json` UCI/HTTP 对手、CLI test/replay、教学包（M6，E009，13 个用例）。
- [ ] **浏览器人工验收**：点击/拖拽/升变/动画/控制台（M3，见 P008）。
- [ ] **Stockfish 完整对局**：沙箱禁管道，需用户本机跑一局（P009）。
- [ ] **新机器三步启动**：`pip install -r requirements.txt` → `python -m chessarena serve`（M6）。
- [ ] 无头吞吐 ≥1000 的**严格回归**门槛（实测 7,067；测试里只断言 ≥200，避免慢机器误报）。

## 15. Environment

- **OS:** Windows；shell 为 PowerShell（`pwsh`）。
- **Python:** 3.12.5；pip 26.2.1；已装 `chess 1.11.2`、`fastapi 0.159.1`、`uvicorn 0.54.0`、`PyYAML 6.0.3`、`starlette 1.9.0`、`websockets 17.3`；**未装** `pytest`、`httpx`。
- **Node:** v24.16.0；npm 可用；**pnpm 不可用**（本方案不需要）。
- **Git:** `C:\Program Files\Git\cmd\git.exe` 可用；身份 `diego3893 <diegozcx@foxmail.com>`；提交 `a7da3df`、`8eeaab2`、`b4a56b5`、`3a5e2c9`、`661522a`、`4effeef`、`e6a70b0`。
- **项目根:** `C:\Users\30130\Desktop\workstation\ChessArena`（本会话沙箱工作区，可直接写）。
- **旧暂存区:** `C:\Users\30130\Documents\deepseek-harness\default-workspace`（`vendor/` 已迁出；`.tgz` 仍在此）。
- **Stockfish:** `thirdparty/stockfish/stockfish-windows-x86-64-universal.exe`（Stockfish 19，103 MB；可被 PowerShell 管道调用）；环境变量 `CHESSARENA_STOCKFISH` / `CHESSARENA_STOCKFISH_ELO` / `CHESSARENA_STOCKFISH_MOVETIME`。
- **编码:** Python stdout `gbk` → 验证中文前 `$env:PYTHONIOENCODING='utf-8'`；CLI 已自带 reconfigure；文件一律 UTF-8。
- **复现命令:** `python -m pip install chess fastapi "uvicorn[standard]" pyyaml`；测试 `python -m unittest discover -s tests -t .`；跑一局 `python -m chessarena play`；起服务 `python -m chessarena serve --port 8000`（浏览器开 `http://127.0.0.1:8000/`）。
- **沙箱注意:**
  1. 用中文字面量做路径匹配可能编码错乱，**用通配符枚举 + `Get-FileHash`** 比对。
  2. `tempfile.TemporaryDirectory()` 在工作区外的系统 temp 里**清理会被拒**（WinError 5）；测试临时目录放工作区内（如 `runs/test-*`）并 `shutil.rmtree(ignore_errors=True)`。
  3. 后台服务用受管 job 起，别用 `Start-Process`；验证完 `job_kill`。
  4. **浏览器启动被沙箱拦截**：`msedge.exe` 无输出、`--dump-dom` 0 字节；前端验收只能人工做（P008）。
  5. **子进程管道被禁**：Python `subprocess`/`popen_uci` 抛 `PermissionError(13)`；需引擎验证时用 `danger-full-access` 跑单条命令（P009）。

## 16. Context Handoff Summary

1. **在做什么**：为一门研讨课搭建单机国际象棋 AI 平台；学生写 AI，平台负责裁判、UI、基线对手与联赛。
2. **为什么这样做**：国际象棋规则库成熟 → python-chess 保正确性；chessground 预构建包保 UI 且零构建；"单一写入口 submit + 返回码重试"降低学生出错成本；前端不含棋规，服务端算 SAN/吃子/合法性。
3. **已完成**：阶段 0–6 全部代码完成；**97 个测试全绿（1 个引擎用例在沙箱内 skip）**；M0–M2、M4、M5 达成；M3（浏览器点一遍）与 M6（新机器装依赖）待用户验收。
4. **最大剩余问题**：没有阻塞；只剩人工验收。
5. **已排除**：npm 构建 chessground（F001）；SAN 与 `drop(x,y,color)`（D005）；联机（D008）；`move()` 别名（D003）；关键词式文档校验（F002）；旧版 python-chess 名（F003）；前端自己判规则（D019）；L4 固定深度（D021）；联赛用线程并发（D023）。
6. **第一个下一步**：用户实机验收 —— `start.bat`（或 `python -m chessarena serve`）→ 页面选「人类 vs Stockfish」下几步、再选「随机 vs 贪心」看机机；`python -m chessarena league --players random,greedy,minimax2` 跑一次小联赛；把结果记入 §14。
5. **已排除**：npm 构建 chessground（F001）；SAN 与 `drop(x,y,color)`（D005）；联机（D008）；`move()` 别名（D003）；关键词式文档校验（F002）；旧版 python-chess 名（F003）；前端自己判规则（D019）；L4 固定深度（D021）。
6. **第一个下一步**：**先请用户重启 `serve` 并刷新页面**，确认 P010 的"卡住"已消失（现在有 3s 心跳与 5s 校准兜底）；随后进入阶段 5 —— `chessarena/league.py`（编排 + 多进程 + ELO + 非法率 + HTML 报告）与 CLI `league`，以 M5 验收。

## 17. Decision / Progress Log

`2026-10-23 00:07 — 调研报告完成（docs/chess-ai-platform-research.md）：选定国际象棋 + python-chess 路线。`
`2026-10-23 00:2x — 使用说明书与 API 规格完成。`
`2026-10-23 00:3x — API 总表定稿；按用户要求统一为 submit()，删除 move 别名。`
`2026-10-23 00:3x — chessground 改为官方预构建包方案（D006），放弃 pnpm 构建路径（F001）。`
`2026-10-23 — 建立 PROJECT_CONTEXT.md；项目根确定为 ChessArena。`
`2026-10-23 01:30 — 全量复检（E003）：依赖已装、代码 0 行、无 git、文档 9 处冲突（P003）、UCI/HTTP 协议缺口（P005）、gbk 编码坑（P004）；新增 §6 阶段划分（M0–M6）与 D010–D013；P001 关闭。`
`2026-10-23 01:4x — 用户拍板：先修文档再写内核、接受 GPL、初始化 git（D014）。阶段 0 完成：P003 九处改写、总表 §15 外部对手协议、vendor 迁入、`a7da3df` 首次提交。`
`2026-10-23 01:5x — 阶段 1 完成（M1）：`chessarena/` 内核 15 模块 + L1/L2 + CLI；32 个 unittest 全绿；random vs greedy 一局 106 半步、0.03 s；补 D015（tuple）、D016（超时策略）、P006（人类不消耗重试）。`
`2026-10-23 02:1x — 阶段 2 完成（M2）：总表 §16 推送协议（快照形状 + 400/409/410 + 7 种 WS 消息）；`web/session.py` 驱动线程 + 广播；FastAPI 7 端点；`Client`（stdlib）；`record` JSONL；14 个集成用例，46 个测试全绿，吞吐 7,067 plies/s；补 D017（单进程一局/单一快照）、D018（服务端驱动 AI）。`
`2026-10-23 02:5x — 阶段 3 代码完成：`web/ui/`（页 676 行 JS/CSS/HTML）零构建引 chessground；服务端补 `history_san`/`captured`/`human`/`paused`/`speed`/`timeout`，`/control` 增 `undo`/`resign`/带选手的 `new`；静态页与 4 个接线用例；55 个测试全绿；补 D019（前端不含棋规）、D020（非法重绘）；P008（Edge 在沙箱内起不来，M3 待人工验收）。`
`2026-10-23 03:2x — 阶段 4 完成（M4）：解压 Stockfish 19；`engines/uci.py` + 五档（L3 深度2、L4 αβ 迭代加深 0.85s、L5 `UCI_Elo`）；L3 ≤0.03s、L4 ≤0.86s、找到 Qxf7#；66 个测试全绿（引擎用例沙箱内 skip）；补 D021（预算制）、D022（UCI 交给 python-chess）、P009（沙箱禁管道）。`
`2026-10-23 04:0x — 用户实测"页面卡住"（P010）：无法复现服务端停步，判定为客户端漏消息无兜底 + 驱动线程可能静默死亡。修复：WS heartbeat（3s 全量快照）、客户端 5s HTTP 校准与旧快照丢弃、驱动 try/except + 空转检测 + 2s 自动重启、`GET /debug`、AI 回合"思考中…"；新增 TestResilience 4 用例，70 个测试 3 轮全绿。`
`2026-10-23 09:2x — 用户要求"UI 里选模型"：顶部加白方/黑方两个下拉（人类 / L1–L5 / 未来 agents）+ 开局按钮，改选即重开；新增 `GET /players` 与快照 `players` 字段；`Session.control("new")` 先建后换（非法写法 400 且原局不变），`resolve_player` 把 KeyError 转 `AgentLoadError`；新增 5 个 players 用例，75 个测试全绿。`
`2026-10-23 10:5x — 用户要求 L5 调强：默认 `UCI_Elo` 1600→2600、每步 0.6→1.0s，并接上 `config.yaml` 的 `stockfish: {elo,movetime,path}`（环境变量优先）。实测 2600 对 L4 42 半步将杀、2200 对随机 46 半步将杀；E010 记录；100 测试全绿。`
`2026-10-23 10:0x — 阶段 5、6 完成：`league.py`（编排/进程池/ELO/非法率/HTML+PGN/续跑）、`core/external.py`（agents.json 的 UCI/HTTP 对手 + TransientError）、CLI `test`/`league`/`replay`、`agents/examples` 三样例、`assignments` 骨架 + `grade.py`、`config.yaml`/`start.bat`/`requirements.txt`/`README.md`；`serve` 支持 `--timeout/--max-retries` 并从 config 取 host/port；97 个测试全绿；补 D023（联赛并发模型）、D024（EngineError vs TransientError）、E008/E009。`
