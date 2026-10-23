# ChessArena · 国际象棋 AI 对战场

单机网页环境：你点着下棋，或者看两个 AI 互打；学生写一个 Python 类就能参赛；
AI 既能被平台调用，也能自己 `game.submit()` 主动落子；内置 5 档陪练；一条命令跑联赛算 ELO。

## 快速开始

```bash
pip install -r requirements.txt
python -m chessarena serve
```

浏览器打开 <http://127.0.0.1:8000/>。Windows 也可以直接双击 **`start.bat`**。
不需要 Node、不需要数据库、不需要 GPU；前端是预构建好的静态文件。

## 页面怎么用

顶部两个下拉框决定谁走哪边：`人类` / `随机 (L1)` / `贪心 (L2)` / `Minimax 深度2 (L3)` / `Minimax 深度3 αβ (L4)` / `Stockfish (L5)`。
两边都选 AI 就是机机观战（可调速、暂停、单步）；两边都选人类就是同机双人。

## 学生：写一个 AI

在 `agents/` 下建 `my_agent.py`：

```python
from chessarena import Agent

class MyAgent(Agent):
    name = "张同学"

    def choose_move(self, state):
        return state.legal_moves[0]     # 先跑通，再写搜索
```

刷新页面，它就出现在下拉框里。自测：

```bash
python -m chessarena test agents/my_agent.py --vs builtin:greedy --games 20
```

## 命令

| 命令 | 作用 |
|---|---|
| `python -m chessarena serve` | 起网页（默认人类 vs 贪心） |
| `python -m chessarena play --white … --black …` | 命令行跑一局并打印 PGN |
| `python -m chessarena test agents/x.py --vs builtin:greedy --games 20` | 批量自测 |
| `python -m chessarena league --players random,greedy,minimax2` | 循环赛 + ELO + HTML 报告 |
| `python -m chessarena replay results/…/pgn/x.pgn` | 终端回放 |
| `python -m unittest discover -s tests -t .` | 跑平台自测 |

## 目录

```
chessarena/        平台本体（core 裁判 / builtin 五档 / web 服务与页面 / engines UCI）
agents/            ★ 学生 AI 放这里（examples 有 3 个样例）
assignments/       ★ 作业模板与评分脚本
vendor/            chessground 预构建产物（前端，零构建）
thirdparty/        chessground 源码 + Stockfish（需解压）
tests/             97 个单元/集成用例
runs/  results/    录像 / 联赛报告（可再生成）
docs/              设计文档：API 总表（SSOT）、API 规格、使用说明书、选型调研
config.yaml        端口、每步时限、重试、联赛参数
```

## 文档

- [API 总表](docs/chessarena-API总表.md) —— 接口的单一事实来源
- [API 规格](docs/chessarena-API规格.md) —— 为什么这样设计
- [使用说明书](docs/chessarena-使用说明书.md) —— 界面、玩法、教学节奏
- [选型调研](docs/chess-ai-platform-research.md) —— 为什么是国际象棋 + python-chess + chessground

## 许可

平台代码供课程使用。`vendor/chessground` 为 GPL-3.0-or-later，`python-chess` 与 `Stockfish` 为 GPL-3.0；
向使用者分发页面时需同时提供对应源码（见 `vendor/chessground/README.md`）。
