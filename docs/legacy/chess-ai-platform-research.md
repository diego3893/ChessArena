# 棋类 AI 对战平台 · GitHub 开源方案调研

> 历史选型调研：其中枚举合法着法等早期接口已被学生接口v2取代，当前实现以[API总表](chessarena-API总表.md)为准。

> 目的：研讨课助教需要一个"能看（UI）、能下（人机/机机）、能接入学生自己 AI、自带基线 AI"的象棋环境。
> 数据来源：GitHub REST API 逐仓库核实（star / license / 最后提交 / 目录结构），下文数字均为实测，非印象。

---

## 一、先把需求翻译成技术要求

| 你的需求 | 技术上意味着什么 | 为什么这是关键 |
|---|---|---|
| ① 有美观的 UI | 前后端分离，棋盘只负责渲染 | 学生不会改 UI，但**一定要能观战**，否则 AI 对弈毫无观赏性 |
| ② 人机 + 机机对战 | 对局循环不区分对手是人还是 bot | AI 一旦写死在对局逻辑里，就做不了机机对战 |
| ③ 给 AI 的 API | 读状态 / 枚举合法着法 / 落子 | **这是平台的核心抽象**，直接决定学生作业难度 |
| ④ 内置 AI | minimax/alpha-beta 基线 + 可选强引擎 | 基线用来"打得过/打不过"，强引擎用来标定 ELO |

一句话结论：**"界面 / 规则 / AI"必须解耦，中间只走一个薄接口。**

由此得到选型思路：不要找"一个大而全的象棋网站"来硬改，而要找**规则库成熟 + 棋盘组件成熟**的积木，自己写中间那层裁判与 Agent 接口。

---

## 二、推荐架构（与选哪种棋无关）

```
┌──────────────┐  WebSocket/HTTP  ┌────────────────┐   Agent 接口   ┌───────────┐
│  浏览器 UI    │ ←──────────────→ │  对局服务(裁判)  │ ←───────────→ │  AI 进程   │
│ 棋盘/走子动画  │                  │ · 持唯一真实状态 │                │ 内置minimax│
│ 状态栏/棋谱    │                  │ · 合法性校验     │                │ 学生 AI    │
└──────────────┘                  │ · 判负/超时/记谱 │                │ Stockfish  │
                                   └────────────────┘                └───────────┘
                                            ↑
                                    ┌───────────────┐
                                    │ 规则引擎(可换) │ ← 换棋种只换这一层
                                    └───────────────┘
```

四条设计要点（做到这几条，需求 ②③④ 自动满足）：

1. **裁判层是唯一真相源。** UI 和学生 AI 都只能"提出"着法，由裁判校验并广播。
2. **人是另一种 Agent。** 人机 = 一个 Agent 是人类（等前端点击）；机机 = 两个都是程序。代码路径完全一致。
3. **状态不可变。** `apply(move)` 返回新 state 而不是原地修改，学生写 minimax 递归会非常干净。
4. **着法用字符串**（国际象棋 `e2e4`、中国象棋 `h2e2`），跨语言、易打印、好调试。

建议接口（Python 版，可直接当作业模板发给学生）：

```python
class Agent:
    """学生只需要实现这一个方法。"""
    name: str = "anonymous"

    def choose_move(self, state: "State") -> str:
        """返回一个合法着法字符串，如 'e2e4'。超时/非法着法 = 判负。"""
        raise NotImplementedError


class State:                       # 平台提供，学生只读
    def fen(self) -> str: ...
    def board(self) -> list: ...           # 二维表示，便于喂给 CNN
    def legal_moves(self) -> list[str]: ...
    def side_to_move(self) -> str: ...
    def is_game_over(self) -> bool: ...
    def result(self) -> str | None: ...
    def apply(self, move: str) -> "State": ...
```

**跨语言技巧**：若裁判层再支持 UCI/UCCI 协议（stdin/stdout 文本），任何语言写的 AI 都能用约 30 行 wrapper 接入。学生用 C++/Rust/Java 也不必改平台。

---

## 三、候选项目（均为实测数据）

### 3.1 国际象棋：规则库与引擎（可直接复用的积木）

| 仓库 | Star | 语言 | License | 最后提交 | 定位 |
|---|---|---|---|---|---|
| [niklasf/python-chess](https://github.com/niklasf/python-chess) | 2892 | Python | GPL-3.0 | 2026-08 | **规则库事实标准**：合法性、将死/逼和、FEN/PGN、UCI 引擎通信全都有 |
| [jhlywa/chess.js](https://github.com/jhlywa/chess.js) | 4431 | TypeScript | BSD-2 | 2026-08 | 前端规则库，可直接在浏览器判定胜负，**License 最友好** |
| [official-stockfish/Stockfish](https://github.com/official-stockfish/Stockfish) | 17046 | C++ | GPL-3.0 | 2026-10 | 最强开源引擎，人机对战"大魔王" |
| [nmrugg/stockfish.js](https://github.com/nmrugg/stockfish.js) | 1222 | C++/WASM | GPL-3.0 | 2026-10 | 引擎编进浏览器，**无后端也能有人机对战** |
| [fairy-stockfish/Fairy-Stockfish](https://github.com/fairy-stockfish/Fairy-Stockfish) | 922 | C++ | GPL-3.0 | 2026-10 | 支持变体规则，象棋类变体可尝试 |

### 3.2 国际象棋：棋盘 UI 组件

| 仓库 | Star | License | 特点 |
|---|---|---|---|
| [lichess-org/chessground](https://github.com/lichess-org/chessground) | 1383 | GPL-3.0 | lichess 官网同款，手感/动画最好，TypeScript |
| [oakmac/chessboardjs](https://github.com/oakmac/chessboardjs) | 2131 | MIT | 最简单，配 chess.js 的教程最多；2024 后基本停更 |
| [shaack/cm-chessboard](https://github.com/shaack/cm-chessboard) | 309 | MIT | 现代 Web Component，无框架依赖，MIT 友好 |

### 3.3 国际象棋：完整应用 / 训练参考

| 仓库 | Star | 语言 | License | 最后提交 | 定位 |
|---|---|---|---|---|---|
| [pychess/pychess](https://github.com/pychess/pychess) | 817 | Python | GPL-3.0 | 2026-10 | 桌面应用：UI + 人机 + 引擎对战 + 变体。⚠ GTK 依赖，**PyGObject 在 Windows 上安装很痛苦** |
| [Zeta36/chess-alpha-zero](https://github.com/Zeta36/chess-alpha-zero) | 2229 | Jupyter | MIT | 2023-03 | AlphaZero 复现，**训练代码可读性最好的参考**（无 UI） |
| [Korchy/chess-deep-rl](https://github.com/Korchy/chess-deep-rl) | 180 | Jupyter | GPL-3.0 | 2024-06 | 另一个 AlphaZero 实现，可对比阅读 |

### 3.4 中国象棋

| 仓库 | Star | 语言 | License | 最后提交 | 定位 |
|---|---|---|---|---|---|
| [XMuli/ChineseChess](https://github.com/XMuli/ChineseChess) | 831 | C++/Qt | GPL-3.0 | 2026-05 | **功能最全的现成应用**：UI + 内置 AI + 人机 + 联机；但 C++/Qt，接 Python AI 要自己搭桥 |
| [xqbase/xqwlight](https://github.com/xqbase/xqwlight) | 246 | JS/C++/Java | GPL-2.0 | 2025-05 | **象棋小巫师**：minimax + alpha-beta 只有几百行，多语言版本齐全，**教学参考首选** |
| [xqbase/eleeye](https://github.com/xqbase/eleeye) | 405 | C++ | LGPL-2.1 | 2026-08 | 经典"象眼"引擎，UCCI 协议 |
| [official-pikafish/Pikafish](https://github.com/official-pikafish/Pikafish) | 2169 | C++ | GPL-3.0 | 2026-10 | 目前最强象棋引擎（Stockfish 血统） |
| [walker8088/cchess](https://github.com/walker8088/cchess) | 74 | Python | GPL-3.0 | 2026-07 | **Python 中国象棋规则库**：FEN、着法生成、AI 示例，中文文档 |
| [sojourners/public-Xiangqi](https://github.com/sojourners/public-Xiangqi) | 362 | Java | GPL-3.0 | 2026-09 | 跨平台**界面程序**，可加载 UCI/UCCI 引擎对弈；正好证明"引擎进程"是象棋界的标准接法 |
| [pychess/pychess-variants](https://github.com/pychess/pychess-variants) | 317 | Python | AGPL-3.0 | 2026-10 | **pychess.org 的服务器端**（aiohttp + TS 前端），原生支持象棋等变体，AI 走外部引擎；成熟但体量大、AGPL |
| [tanliyon/gym-xiangqi](https://github.com/tanliyon/gym-xiangqi) | 38 | Python | LGPL-3.0 | 2023-02 | Gym 环境 + 自带 GUI，可"与自己的 agent 对弈" |
| [qwas-zx/chinese-chess-game](https://github.com/qwas-zx/chinese-chess-game) | 0 | Python/Flask | MIT | 2026-09 | 有 `/api/state`、`/api/move`、`/api/valid_moves` 的清晰 REST 接口，**结构最贴近本需求**；但 0★，仅供读码参考 |
| [Trussin/Chinese-Chess-AI](https://github.com/Trussin/Chinese-Chess-AI) | 123 | Python | 无 | 2018-12 | MCTS + 神经网络自对弈，**无 LICENSE，不能分发** |

### 3.5 通用框架（两种棋都覆盖）

| 仓库 | Star | License | 定位 |
|---|---|---|---|
| [google-deepmind/open_spiel](https://github.com/google-deepmind/open_spiel) | 5550 | Apache-2.0 | 统一 API，**同时内置 chess 与 xiangqi**（已核实 `open_spiel/games/xiangqi/xiangqi.cc`），自带 MCTS/CFR/alpha-beta 示例 |
| [Farama-Foundation/PettingZoo](https://github.com/Farama-Foundation/PettingZoo) | 3538 | MIT | 多智能体 RL 标准接口，`classic/chess_v6` 确实存在（已核实 `pettingzoo/classic/chess/chess.py`，底层用 python-chess） |
| [boardgameio/boardgame.io](https://github.com/boardgameio/boardgame.io) | 12470 | MIT | 回合制游戏框架 + React 前端 + 自带 MCTS bot + 联机 |

> **关键分界**：`open_spiel` / `PettingZoo` 只解决 ③④（规则 + 算法接口），**不含 UI**，解决不了 ①。
> `boardgame.io` 反过来：解决 ①② 和联机，但内置 bot 很弱，也没有现成的象棋规则实现。
> `public-Xiangqi`、`pychess-variants` 是"有 UI、缺 AI"的空壳，靠外部引擎补；`Stockfish`/`Pikafish`/`eleeye` 是"有 AI、缺 UI"的纯引擎。**两组拼起来才是一个平台**——这正是你要做的事。

> **一个很值得复用的观察**：中国象棋世界的事实标准 AI 接口是 **UCCI**（不是 UCI）——Pikafish、eleeye 都按它实现，public-Xiangqi 干脆就是个 UCCI 加载器。你的平台只要支持 UCCI，学生用任何语言写的 AI 都能直接接进来；国际象棋同理，走 UCI。这是"需求③"最省事的实现方式，也是第二节那个"跨语言技巧"的现实依据。

---

## 四、国际象棋 vs 中国象棋：选型对工作量的真实影响

这是最该先拍板的一件事，先说硬结论：

> **国际象棋有成熟到"一个 import 全解决"的规则库；中国象棋没有"fork 一下就能用"的美观 Web 平台。**
> 中国象棋的高星项目里，XMuli/ChineseChess（831★）是 Qt 桌面应用，public-Xiangqi（362★）是 Java 引擎加载器，唯一成熟的 Web 平台 pychess-variants（317★）是 AGPL 的大型工程——改造成本都高于自己搭。

| 维度 | 国际象棋 | 中国象棋 |
|---|---|---|
| 规则库成熟度 | ⭐⭐⭐⭐⭐ `import chess` 全解决 | ⭐⭐ 需自己验证 |
| 胜负判定坑 | 少（将死/逼和/50 步/三次重复，库已处理） | 多（长将长捉、**困毙算输不算和**、飞将、过河兵） |
| 现成 Web 平台 | 多，且可直接 fork | 极少，且都是重工程（AGPL/无授权） |
| 学生 AI 参考资料 | 极多（AlphaZero 复现、教材、论文） | 少（主要靠中文社区） |
| 学生熟悉度（国内课堂） | 一般 | 高 |

**建议**：
- 课程重点是**搜索算法 / 博弈树**（minimax、alpha-beta、迭代加深、置换表）→ 两种棋都行，**中国象棋学生参与度更高**，但你要多花约 30% 时间在规则正确性上。
- 课程重点是**强化学习 / self-play / AlphaZero** → **强烈建议国际象棋**，工具链齐全得多。
- **还没定**：把架构做成"Game 是插件"，用国际象棋先跑通端到端，再决定要不要加中国象棋。换棋种只换规则层，UI 与 Agent 接口不动。

---

## 五、三个落地方案

### 方案 A：python-chess + FastAPI + chessground / cm-chessboard（推荐）
- **复用**：规则 100%，UI 组件 90%，只写裁判层 + Agent 层（约 600–800 行）
- **工期**：3–5 天出可用版本
- **内置 AI**：自写 minimax（弱，教学基线）+ Stockfish via UCI（强，人机大魔王）
- **风险**：GPL-3.0（校内用无所谓）

### 方案 B：cchess + 同一套前后端骨架（中国象棋版）
- **复用**：规则约 80%（cchess 有 FEN 与着法生成，长将/困毙要自己补）
- **工期**：5–8 天
- **UI 参考**：qwas-zx 的棋盘与动画（读码），AI 教学参考 xqwlight（几百行看懂 alpha-beta）
- **不建议**直接 fork XMuli/ChineseChess：Qt/C++ 桌面，改造成 Web + Python 接入的成本高于重写

### 方案 C：open_spiel / PettingZoo + 自建前端（科研向）
- **适合**：课程要教 MCTS / CFR / self-play，需要标准基线算法
- **代价**：UI 从零写（2–3 天）；两个库的接口学习成本高于 python-chess
- **优势**：`open_spiel` 一套代码同时覆盖 chess 和 xiangqi，正好对应你"还没定棋种"

---

## 六、坑与注意事项（先看，省返工）

1. **License 传染性**：python-chess、chessground、Stockfish、Pikafish 都是 GPL-3.0；pychess-variants 是 AGPL-3.0（更严格）。校内教学、开源发布都没问题；若将来想闭源分发，规则层换 chess.js（BSD-2），UI 换 chessboardjs / cm-chessboard（MIT）。
2. **无 LICENSE 的项目不能直接分发给学生**：`Trussin/Chinese-Chess-AI`、`pengjiu/ChineseChess`、`xiongfang/Chinese-Chess`、`TaylorPzreal/chinese-chess` 均无 LICENSE 文件，默认"保留所有权利"。
3. **中国象棋重复局面规则**：多数开源实现只做"三次重复判和"，与亚洲规则（长将判负）不同。**必须在规则文档里写死**，否则学生会拿"我的 AI 应该赢"来争论。
4. **困毙（stalemate）**：国际象棋是**和棋**，中国象棋是无子可走的一方**输棋**。这是学生最常写错的一条。
5. **学生 AI 的失控兜底**：裁判层必须有单步超时（如 3s）、总时长限制、非法着法判负、异常捕获。否则一个死循环会卡死整个对局服务。
6. **`gym-xiangqi` 用的是旧版 `gym`**（2023-02 后未更新），与 `gymnasium` API 不兼容。
7. **不要直接改 lichess（lila）**：Scala 微服务集群，为改一个课堂作业去读它不划算。

---

## 七、下一步

需要你拍板三件事，我就能直接开工：

1. **棋种**：国际象棋 / 中国象棋 / 两个都要（先跑通一个）
2. **学生 AI 的语言**：Python（推荐，能对接 PyTorch）/ 任意语言（走 UCI 协议）/ JS
3. **是否需要两台电脑联机对战** —— 需要则方案 A 要加 WebSocket 房间逻辑

拍板后我先给一个**可运行的最小闭环**：棋盘 + 人机 + 机机 + minimax 基线 + 学生 Agent 模板，之后再逐步加计时、ELO 联赛、棋谱回放。
