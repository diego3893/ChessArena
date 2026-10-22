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

**Confirmed（2026-10-23 复检）：**

- **代码 0 行**：整个 `ChessArena` 下 0 个 `.py` 文件，不存在 `chessarena/` 包。
- **依赖已就位**：`chess 1.11.2`、`fastapi 0.159.1`、`uvicorn 0.54.0`、`PyYAML 6.0.3`、`websockets` 均可 import；`pytest` / `httpx` 未装。
- **文档 4 份**位于 `docs/`。三份设计文档都已是"submit 唯一写入口"，但彼此还有 **9 处细节冲突**（P003：说明书 6 处 / 规格 3 处），且总表缺"UCI/HTTP 外部对手注册"一节（P005）。
- **chessground**：`thirdparty/chessground/` 是 shallow clone（`b4f6050` / `master` / `v10.5.0` / GPL-3.0-or-later），含 `src/`、`assets/*.css`、LICENSE，**不含 `dist/`**。
- **预构建产物未迁入**：仍躺在旧暂存区 `default-workspace/vendor/chessground/`（`dist/chessground.min.js` 33,291 B、3 套 CSS、LICENSE、package.json）。
- **Stockfish 未解压**：`thirdparty/stockfish-windows-x86-64-universal.zip` 81,431,614 B，SHA256 `3C8BF1F9…C30B48A7`，内含 `stockfish/stockfish-windows-x86-64-universal.exe`（103,046,300 B）+ `Copying.txt`。
- **无版本控制**：`ChessArena` 无 `.git`；父目录 `workstation` **也不是** git 仓库（旧记录有误，已纠正）。
- **写权限问题已消失**：当前 DSH 沙箱工作区就是 `ChessArena`（workspace-write），可直接创建/修改文件。
- **中文输出会乱码**：本机 `sys.stdout.encoding == 'gbk'`，`print("中文")` 变乱码；`PYTHONIOENCODING=utf-8` 后正常（D012 / P004）。

**Current assessment：**

- 设计阶段实质已收敛：接口 SSOT 稳定，可以动代码。剩余不确定项（UI 许可证 P002、文档修订 P003/P005）**都不阻塞内核**。
- 阶段划分见 §6。**当前位置：阶段 0 收尾 → 阶段 1 起点。**

**Main issue：**

- 唯一实质风险是"0 行代码"；其余为小项（文档修订、vendor 迁入、许可证确认）。

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
| **0 · 文档与资源冻结** | 4 份文档对同一接口只有一种说法；前端产物落到项目内 | **M0**：P003 的 9 处冲突改完（`place/commit/"white"/on_opponent_move` 零残留）；P005 的 UCI/HTTP 注册协议补进总表；`vendor/chessground/` 迁入；GPL 结论（P002）记录为决策 | S · 半天 | **进行中**（冲突已逐条定位，未修） |
| **1 · 裁判内核 + 命令行闭环** | `chessarena` 包最小纵向切片：`Game.submit` 全返回码、原子性、重试预算、超时、终局判定、PGN；内置 L1/L2 | **M1**：`python -m chessarena play --white builtin:random --black builtin:greedy` 跑完整局并打印 PGN；`unittest` 覆盖 5 个返回码 + 原子性 + 3 种终局；中文不乱码 | M · 600–800 行 | **下一步**（未开始） |
| **2 · 运行模式 + Web 服务 + Client** | `live` / `headless` / `record` 三模式；FastAPI 3 端点 + WebSocket 推送；跨进程 `Client` 方法名同构 | **M2**：无头实测 ≥1000 plies/s；`curl` 三端点可用；`Client` 与同进程 API 同名同返回 | M | 未开始 |
| **3 · 前端（chessground 零构建）** | 引 vendor 的 `min.js` + CSS：合法点高亮、升变、上一步、将军、SAN 列表、时钟、悔棋、翻转、导出 PGN；人机 + 机机（调速/暂停/单步） | **M3**：浏览器人机对局可完成并正确判负；机机可观战；控制台零报错 | L | 未开始（前置：M0 的 vendor 迁入、P002 结论） |
| **4 · 五档内置 + Stockfish** | L3 minimax2 / L4 minimax3+alpha-beta（各独立 50–150 行）；解压 Stockfish 走 UCI，配 ELO/时限 | **M4**：五档在 UI 中可选；实测每步耗时写入文档（L4 中局 ≤1s）；Stockfish 冒烟对局通过 | M | 未开始（可与阶段 3 并行） |
| **5 · 联赛 + ELO + 报告** | 循环赛、随机开局、并发、ELO、**非法率列**、`results/league-*.html` + PGN 打包、断点续跑 | **M5**：一条命令跑 L1–L4 循环赛并生成 ELO 表 | M | 未开始（依赖 M2） |
| **6 · 教学交付** | `agents/examples/` 3 个样例、`assignments/` 骨架 + 评分脚本、`requirements.txt`、`start.bat`、给学生的一页调用约定 | **M6**：新机器按 README 三步启动；3 个样例通过自测命令 | S–M | 未开始 |

**依赖**：0 → 1 → 2 → 3；4 依赖 1；5 依赖 2；6 最后。**里程碑 ↔ 需求**：M1↔R3、M2↔R5、M3↔R1/R2、M4↔R4、M5↔"一条命令出 ELO"、M6↔教学使用。

**当前阶段判定**：阶段 0 只剩 S 级收尾（文档 9 处 + P005 补节、vendor 迁入、GPL 结论），可与阶段 1 同期启动；**建议下一动作是阶段 0 的文档修订 + 阶段 1 的包骨架**。

## 7. Important Files

| File | Purpose | Notes |
|---|---|---|
| `docs/chessarena-API总表.md` | **接口单一事实来源**（§0–§14） | 实现照此写；与其他文档冲突时以它为准（D010） |
| `docs/chessarena-API规格.md` | 设计意图、返回码语义、重试规则 | 主体一致；3 处细节与总表冲突，见 P003 |
| `docs/chessarena-使用说明书.md` | 产品形态、界面线框、五档难度、教学节奏 | **6 处旧设计残留，见 P003** |
| `docs/chess-ai-platform-research.md` | GitHub 选型调研（星数/License 实测） | 调研期结论；其中"非法着法判负"已被 D004 取代 |
| `thirdparty/stockfish-windows-x86-64-universal.zip` | L5 引擎 | 未解压；内含 `stockfish/…universal.exe` |
| `thirdparty/chessground/` | 参考源码（GPL-3.0，shallow clone v10.5.0） | 仅供阅读；**不需要构建**，无 `dist/` |
| `<old-ws>/vendor/chessground/` | 实际前端要引的产物（min.js + 3 CSS） | 待迁入 `ChessArena/vendor/chessground/` |
| `chessarena/`（待建） | 平台包：`core/` 裁判、`builtin/` 五档、`web/` 服务、`cli.py` | 阶段 1 起 |
| `tests/`（待建） | `unittest` 用例 | 阶段 1 起 |

`<old-ws>` = `C:\Users\30130\Documents\deepseek-harness\default-workspace`（旧暂存区，只读式取用）。

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

### D013 — 建议为 `ChessArena` 初始化 git，排除大文件

**Decision（待用户确认）:** `git init` + 首次提交文档与上下文；`.gitignore` 排除 `thirdparty/*.zip`、`thirdparty/chessground/`、`runs/`、`results/`。
**Reason:** 现在无版本控制，多阶段实现无法 diff / 回滚。
**Evidence:** E003（`ChessArena` 无 `.git`，父目录亦非仓库）。
**Implication:** 若同意，在阶段 1 开工前完成，之后每阶段一次提交。
**Status:** Plan

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

## 11. Bugs / Open Problems

### P001 — 删除 `ChessArena/chessground` 时 Windows 报"文件夹正在使用"

**Status:** **Resolved（失效）**。用户已把克隆移入 `thirdparty/chessground/` 且可正常读取/枚举，不再需要删除该目录。
**Keep for history:** 无 `.lock`、`git rev-parse` 正常，当时最可疑的是终端工作目录停留在内部。若将来再次出现，先关窗口/资源管理器再删。

### P002 — chessground 为 GPL-3.0，授权尚未确认

**Symptoms:** 引入 chessground 会使前端受 GPL-3.0-or-later 约束。
**Known facts:** `package.json` 与 README 均为 `GPL-3.0-or-later`，README 明说"必须向使用者发布源码"。
**Assessment:** 校内教学 + 开源课程仓库完全可接受；闭源分发不可。
**Next investigation:** 用户一句话确认即可；不接受则改自写 SVG 棋盘（约 400 行，阶段 3 的替代路线）。
**Impact:** 阻塞阶段 3 开工（不阻塞阶段 1/2）。**Decision gate：M0 前定。**

### P003 — 文档内部冲突 9 处（说明书 6 / 规格 3），需按 D010 收敛

**《使用说明书》（6 处）：**
1. L193：`state.turn` 写作 `"white"`/`"black"`，总表 §4 为 `"w"`/`"b"`。
2. L229–230：`board = game.board` 注释为"棋盘：可逐格读写（编辑器语义）"，与 Board 只读矛盾。
3. L310：仍有 `place()` / `commit()`（总表无此接口，D003 已废）。
4. L318：判定规则表"返回非法着法 → 该方判负"，与 D004 三次重试矛盾。
5. L397：§八 列表残留 "（`move` / `drop` / `place`）"。
6. L308：非法着法"抛 `IllegalMoveError` / 返回 409"，应为"返回码 `-1`（HTTP 400）+ 原子回滚"。

**《API规格》（3 处）：**
7. L115：`over_reason` 取值 `checkmate/stalemate/threefold/fifty/forfeit/timeout`，总表另有 `insufficient`、`resign`、`retry_exhausted`（无 `forfeit`）。
8. L119：写成 `game.on_opponent_move(callback)`，总表统一为 `on("opponent_move", cb)`。
9. L127：`board.piece_at()` 返回 `'P' / '.' / None`，总表为 `"P"`/`"p"`/`"."`（无 `None`）。

**Fix:** 阶段 0 按 D010 逐处改写为总表口径（总数 9，改完用逐条对账复查）。
**Impact:** 学生会读到错误调用约定，必须在发作业前修掉。

### P004 — 本机 Python stdout 为 gbk，中文输出乱码

**Symptoms:** `print("中文测试")` → 乱码；`sys.stdout.encoding == 'gbk'`。
**Fix:** D012（CLI reconfigure + 显式 encoding）。作文本写入时用 `encoding='utf-8'`。
**Impact:** 低（有确定绕法），但每个入口都要记得加。

### P005 — 总表缺"UCI/HTTP 外部对手注册"协议

**Symptoms:** 《使用说明书》§三 写了 `agents/agents.json`（`type: uci | http`、`cmd`、`url`、超时、`{"move": ...}` 载荷），但《API总表》§10 只列 `human` / `builtin:*` / 文件路径 / 实例，**没有** UCI 与 HTTP 对手的注册与线协议。
**Assessment:** Stockfish（阶段 4）与"GPU 上的神经网络"（阶段 2）都走这条路，没有 SSOT 会导致实现与文档各写一套。
**Fix:** 阶段 0 在总表补一节（`§15 外部对手注册`）：`agents.json` 字段、UCI 握手序列（`uci`/`isready`/`position`/`go`/`bestmove`）、HTTP 请求/响应 JSON。
**Impact:** 中；阻塞阶段 2 的 `Client`/HTTP 对手与阶段 4 的 UCI 适配，不阻塞阶段 1。

## 12. Current Working Set

- **Files currently being changed:** `PROJECT_CONTEXT.md`（本轮全量修订 + 阶段划分）。
- **Functions/components in focus:** 阶段 1 的 `Result` / `Board` / `State` / `Game.submit` 校验链。
- **Immediate issue:** 无阻塞项；阶段 0 的 3 个收尾项 + 阶段 1 的包骨架。
- **Current hypothesis:** M1（命令行跑完整局输出 PGN）能在 600–800 行内达成，且是最快验证 API 手感的路径。
- **Next check:** 写 `Game.submit` 时用具体棋例固定以下语义：`-2` vs `-1` 的边界（格式差 vs 不合法）、升变串 `e7e8q` 的接受/拒绝规则、人类路径不消耗重试次数。

## 13. Next Actions

**阶段 0（先做，S）**
- [ ] 按 D010 修 P003 的 9 处（说明书 6 + 规格 3），并把 P005 的"外部对手注册"补进总表；修完按 F002 的对账法复查（逐条对总表，别只 grep）。
- [ ] 把 `<old-ws>/vendor/chessground/` 迁入 `ChessArena/vendor/chessground/`，并核对 `dist/chessground.min.js` 仍是 33,291 B。
- [ ] 用户确认 P002（GPL 可接受）与 D013（git init）。

**阶段 1（随后，M）**
- [ ] 建包骨架：`chessarena/{__init__,core/{rc,result,board,state,game,agent,moves},builtin/{random,greedy},cli}.py`。
- [ ] `Game.submit` 全链：格式校验 → 轮次 → 终局 → 合法性 → 原子提交 → 事件广播。
- [ ] 重试预算（D009）+ 超时 + `forfeit`/`random` 两种处置。
- [ ] 终局判定对齐 python-chess（将杀/逼和/三次重复/50 步/子力不足）+ `pgn()`。
- [ ] L1 random / L2 greedy（各 ≤150 行，带教学注释）。
- [ ] `tests/` 用 unittest 覆盖 5 个返回码、原子性、3 类终局；`PYTHONIOENCODING=utf-8` 下验证中文。
- [ ] **M1 验收**：`python -m chessarena play --white builtin:random --black builtin:greedy` 出完整 PGN。

**阶段 2+（排期待启动）**
- [ ] 三模式 + FastAPI 3 端点 + WebSocket 推送 + `Client`（M2）。
- [ ] vendor 前端页面（M3，前置 P002）。
- [ ] L3/L4 + Stockfish 解压与 UCI 适配（M4，可并行）。
- [ ] 联赛 + ELO + 报告（M5）。
- [ ] 教学包：examples / assignments / requirements.txt / start.bat / 调用约定（M6）。

## 14. Validation Status

- [x] **文档存在且可读**：`docs/` 4 份齐全（2026-10-23）。
- [x] **依赖可 import**：chess / fastapi / uvicorn / yaml / websockets（E003）。
- [x] **chessground 产物完整性**（内容校验，E001）：含 `export {` 与 `Chessground`，无 sourcemap 引用；产物仍在暂存区未迁入。
- [x] **Stockfish 包可读**：zip 完整解出目录树，含 universal.exe 与 Copying.txt。
- [ ] **文档零冲突**：现有 9 处（P003）+ 1 处缺口（P005）——**未通过**。
- [ ] 规则内核实现与单元测试。
- [ ] 端到端：命令行一局输出 PGN（M1）。
- [ ] 无头吞吐 ≥1000 plies/s（M2）。
- [ ] 页面联调：人机 + 机机（M3）。
- [ ] Stockfish 可执行性（zip 未解压）与五档耗时（M4）。
- [ ] 联赛一条命令出 ELO（M5）。

## 15. Environment

- **OS:** Windows；shell 为 PowerShell（`pwsh`）。
- **Python:** 3.12.5；pip 26.2.1；已装 `chess 1.11.2`、`fastapi 0.159.1`、`uvicorn 0.54.0`、`PyYAML 6.0.3`、`starlette 1.9.0`、`websockets`；**未装** `pytest`、`httpx`。
- **Node:** v24.16.0；npm 可用；**pnpm 不可用**（本方案不需要）。
- **Git:** `C:\Program Files\Git\cmd\git.exe` 可用；项目自身未初始化仓库（D013）。
- **项目根:** `C:\Users\30130\Desktop\workstation\ChessArena`（本会话沙箱工作区，可直接写）。
- **旧暂存区:** `C:\Users\30130\Documents\deepseek-harness\default-workspace`（`vendor/` 与 `.tgz` 在此；写入需提权，只作取用）。
- **编码:** Python stdout `gbk` → 验证中文前 `$env:PYTHONIOENCODING='utf-8'`；文件一律 UTF-8。
- **复现命令:** `python -m pip install chess fastapi "uvicorn[standard]" pyyaml`（均已满足）。
- **沙箱注意:** 用中文字面量做路径匹配可能编码错乱，**用通配符枚举 + `Get-FileHash`** 比对。

## 16. Context Handoff Summary

1. **在做什么**：为一门研讨课搭建单机国际象棋 AI 平台；学生写 AI，平台负责裁判、UI、基线对手与联赛。
2. **为什么这样做**：国际象棋规则库成熟 → python-chess 保正确性；chessground 预构建包保 UI 且零构建；"单一写入口 submit + 返回码重试"降低学生出错成本。
3. **已完成**：4 份设计/API 文档；依赖全部装好；chessground 源码克隆与预构建产物都到手（产物未迁入）；Stockfish 包已下载；阶段划分（§6）已定。
4. **最大剩余问题**：代码为 0 行——`chessarena/` 包尚未创建；其次是文档 9 处冲突（P003）、UCI/HTTP 协议缺口（P005）与 GPL 确认（P002）。
5. **已排除**：npm 构建 chessground（F001）；SAN 与 `drop(x,y,color)` 着法格式（D005）；联机（D008）；`move()` 别名（D003）；关键词式文档校验（F002）。
6. **第一个下一步**：阶段 0 —— 按 D010 修文档 9 处、补 P005 一节、迁 vendor；紧接阶段 1 —— 建包骨架并实现 `Game.submit`，以 M1（命令行一局出 PGN）验收。

## 17. Decision / Progress Log

`2026-10-23 00:07 — 调研报告完成（docs/chess-ai-platform-research.md）：选定国际象棋 + python-chess 路线。`
`2026-10-23 00:2x — 使用说明书与 API 规格完成。`
`2026-10-23 00:3x — API 总表定稿；按用户要求统一为 submit()，删除 move 别名。`
`2026-10-23 00:3x — chessground 改为官方预构建包方案（D006），放弃 pnpm 构建路径（F001）。`
`2026-10-23 — 建立 PROJECT_CONTEXT.md；项目根确定为 ChessArena。`
`2026-10-23 01:30 — 全量复检（E003）：依赖已装、代码 0 行、无 git、文档 9 处冲突（P003）、UCI/HTTP 协议缺口（P005）、gbk 编码坑（P004）；新增 §6 阶段划分（M0–M6）与 D010–D013；P001 关闭。`
