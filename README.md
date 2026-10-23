# ChessArena · 单机国际象棋 AI 对战场

本地起一个网页，**你点着下棋、或者看两个 AI 互相打**；学生写一个 Python 类就能参赛；
AI 既能被平台调用，也能自己 `game.submit()` 主动落子；内置 5 档陪练；一条命令跑联赛算 ELO。

- **单机、零构建**：Python + 静态前端（chessground 预构建产物），不装 Node、不用数据库、不用 GPU。
- **规则不出错**：走法生成、将杀/逼和/三次重复/50 步全部交给 python-chess，平台只做裁判。
- **失败不炸**：非法着法返回 `-1` 让你重试（最多 3 次，共享 3 秒预算），不会因为一个笔误毁掉整节课。
- **同一套代码两种场合**：`live=False` 无头训练（每秒数千步），`live=True` 直接上台对战。
- **110 个自动化测试**，含真实 HTTP/WebSocket 集成、联赛报告与文档契约。

---

## 快速开始

```bash
pip install -r requirements.txt
python -m chessarena serve
```

浏览器打开 <http://127.0.0.1:8000/>。Windows 也可以直接双击 **`start.bat`**（会自动装依赖并打开浏览器）。

要求：Python 3.10+（开发环境 3.12）。

---

## 页面怎么用

顶部两个下拉框决定**谁走哪边**：

```
白方 [人类 ▾]  vs  黑方 [贪心 (L2) ▾]   [开局]
```

- 可选：`人类`、`随机 (L1)`、`贪心 (L2)`、`Minimax 深度2 (L3)`、`Minimax 深度3 αβ (L4)`、`Stockfish (L5)`；
  `agents/` 里的学生 AI（以及 `agents/agents.json` 注册的 UCI/HTTP 对手）也会自动出现。
- 改任一下拉框或点「开局」，就按新配置重开一局。

| 白方 | 黑方 | 玩法 |
|---|---|---|
| 人类 | 任一 AI | 人机对战 |
| AI | AI | 机机观战（底部出现速度 0.25–20×、暂停、单步） |
| 人类 | 人类 | 同机双人（裁判替你们判合法） |

对局中有：合法落点、拖拽/点击落子、升变四选一、上一步高亮、将军提示、SAN 记谱、吃子、悔棋、认输、翻转、导出 PGN、复制 FEN。
AI 在算时状态栏显示「黑方思考中…」；页面 5 秒没收到推送会自己用 HTTP 校准，不会假装卡住。

---

## 写你的 AI（5 分钟）

在 `agents/my_agent.py` 里：

```python
from chessarena import Agent

class MyAgent(Agent):
    name = "张同学"

    def choose_move(self, state):
        return state.legal_moves[0]     # 先能下棋，再写搜索
```

保存后刷新页面，下拉框里就有它了。自测：

```bash
python -m chessarena test agents/my_agent.py --vs builtin:greedy --games 20
# 10 胜 2 和 8 负 · 胜率 50.0% · 平均每步 0.42s · 最长 1.8s
```

- 完整的学生接口（`Agent` / `State` / `Result` / `Game` / `Client`）见 **[学生 API](docs/chessarena-学生API.md)**。
- 三个样例在 `agents/examples/`：`random_agent.py`（10 行）、`minimax_agent.py`（αβ 深度 3，注释详尽）、`http_client_agent.py`（跨进程）。
- 作业骨架与评分脚本在 `assignments/`。

---

## 命令

| 命令 | 作用 |
|---|---|
| `python -m chessarena serve [--port 8000] [--white …] [--black …]` | 起网页 |
| `python -m chessarena play --white builtin:random --black builtin:minimax3 --pgn runs/x.pgn` | 命令行跑一局，打印 PGN |
| `python -m chessarena test agents/x.py --vs builtin:greedy --games 20` | 批量自测：胜率 / 平均每步 / 最长 |
| `python -m chessarena league --players random,greedy,minimax2 --rounds 2` | 循环赛 + ELO + HTML 报告 |
| `python -m chessarena replay results/…/pgn/x.pgn [--board] [--delay 0.3]` | 终端回放 |
| `python -m unittest discover -s tests -t .` | 跑平台自测（110 个用例） |

### 联赛输出

```bash
python -m chessarena league --players random,greedy,minimax2,agents/张同学.py \
    --rounds 2 --openings 8 --concurrent 4
```

- 每对选手下 `2*rounds` 局，黑白各一次；开局先随机走 `openings` 步，避免所有对局一模一样。
- 报告：`results/league-<时间>/index.html` —— ELO 榜、胜/和/负、得分率、**非法率**、平均每步，以及每局 PGN 下载。
- 进度实时打印在终端；中断后重跑同一条命令会**跳过已完成的局**。

---

## 目录

```
chessarena/          平台本体
  core/              裁判 Game、Board、State、Agent、Arena、录像、外部对手
  builtin/           五档内置：random / greedy / minimax2 / minimax3 / stockfish
  engines/           UCI 引擎适配（Stockfish）
  web/               FastAPI 服务 + WebSocket；ui/ 是页面（index.html / app.js / style.css）
  league.py          循环赛 + ELO + HTML 报告
  client.py          跨进程 Client
  cli.py             play / serve / test / league / replay
agents/              ★ 学生 AI 放这里（examples/ 三个样例）
assignments/         ★ 作业骨架（eval / minimax）与 grade.py 自评
vendor/              chessground 预构建产物（前端，零构建）
thirdparty/          chessground 源码 + Stockfish（已解压）
tests/               110 个单元 / 集成 / 文档契约用例
runs/  results/      录像、日志、联赛报告（可再生成）
docs/                设计文档
config.yaml          端口、每步时限、重试、联赛参数、L5 强度
start.bat            Windows 一键启动
```

---

## 配置

`config.yaml` 里最常用的几项：

```yaml
server: {host: 127.0.0.1, port: 8000}
game:
  timeout: 3.0            # 每步总时长（含全部重试）
  max_retries: 3          # 一步最多被拒几次
league: {rounds: 2, openings: 8, max_concurrent: 4}
stockfish:
  elo: 2600               # L5 强度，1320–3190
  movetime: 1.0           # L5 每步思考秒数
```

临时调档也可以走环境变量（优先级高于配置文件）：`CHESSARENA_STOCKFISH_ELO=1800`、`CHESSARENA_STOCKFISH_MOVETIME=0.6`。

---

## 文档

| 文档 | 给谁看 | 内容 |
|---|---|---|
| [学生 API](docs/chessarena-学生API.md) | 学生 | 只列你会用到的接口与常见错误 |
| [API 总表](docs/chessarena-API总表.md) | 实现者 | 接口的单一事实来源（SSOT），含 HTTP/WebSocket 协议 |
| [API 规格](docs/chessarena-API规格.md) | 实现者 / 助教 | 为什么这样设计、返回码语义、重试规则 |
| [使用说明书](docs/chessarena-使用说明书.md) | 助教 / 学生 | 界面、玩法、教学节奏、五档难度 |
| [选型调研](docs/chess-ai-platform-research.md) | 决策者 | 为什么是国际象棋 + python-chess + chessground |

---

## 常见问题

**端口被占用？** `python -m chessarena serve --port 8001`，或改 `config.yaml` 的 `server.port`。

**网页上点了没反应 / AI 不走？** 看状态栏：显示「思考中…」说明服务端在算（默认每步最多 3 秒）；仍不动就看服务器终端有没有 `[chessarena]` 开头的日志，浏览器 F12 看控制台，或访问 `http://127.0.0.1:8000/debug`（驱动线程状态、空转次数、最近异常）。

**L5 的 Stockfish 打不开？** 引擎随包在 `thirdparty/stockfish/`（zip 解压即可）。路径按 `CHESSARENA_STOCKFISH` → `config.yaml` 的 `stockfish.path` → 默认路径找。

**我的 AI 一步要 10 秒，一直判负？** 每步限时 3 秒（含重试）。降搜索深度、加 alpha-beta 或着法排序；`config.yaml` 的 `game.timeout` 可放宽，但联赛里所有 AI 用同一值。

**想换中国象棋？** 规则层是插件：新增一个 `Game` 实现（走法生成、胜负、FEN），UI 的棋盘要重画。这是 v2 的事。

**前端能改吗？** `chessarena/web/ui/` 是三个静态文件，没有任何构建步骤；改完刷新即可。

---

## 许可

- 平台代码供课程使用。
- `vendor/chessground` 为 **GPL-3.0-or-later**（页面分发时须同时提供对应源码，见 `vendor/chessground/README.md`）。
- `python-chess` 与 `Stockfish` 均为 **GPL-3.0**。
