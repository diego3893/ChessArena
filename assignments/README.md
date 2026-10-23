# 学生 AI 作业

## 交什么

把 `agents/my_agent.py` 交上来（一个文件，内含 `class MyAgent(Agent)`）。
平台会自动在页面下拉框里列出它，也可以直接命令行自测。

## 四份骨架

| 文件 | 阶段 | 要做的事 |
|---|---|---|
| `eval_stub.py` | 第 2 周 | 补全 `evaluate(state)`：子力 + 位置 |
| `minimax_stub.py` | 第 3 周 | 补全 minimax 递归（`search`） |
| （`agents/examples/minimax_agent.py`） | 第 4 周 | 读 alpha-beta 的写法，加到自己的搜索里 |
| `grade.py` | 第 5 周起 | 自评/互评：跟基线打固定局数，给出胜率与非法率 |

## 自测命令

```bash
# 跟贪心打 20 盘，看胜率与平均每步耗时
python -m chessarena test agents/my_agent.py --vs builtin:greedy --games 20

# 跟同学的 AI 打 10 盘
python -m chessarena test agents/my.py --vs agents/li.py --games 10

# 自评脚本（会写一份 JSON 到 runs/）
python assignments/grade.py agents/my_agent.py --games 12
```

## 评分口径（建议）

1. **合法性**：非法率 = 被拒次数 / (落子数 + 被拒次数)。超过 5% 先扣分——这类问题通常是学生自己的合法性判断或解码器有误（平台不提供候选动作）。
2. **对基线胜率**：`vs builtin:greedy` 与 `vs builtin:minimax2` 各打 10 盘，取平均得分。
3. **稳定性**：单步耗时不能撞 3s 上限；`test` 命令输出的"最长"就是你要盯的数。
4. **可读性**：搜索代码要能讲清楚（评估函数、剪枝、着法排序）。

## 注意

- 不要在 `choose_move` 里既 `self.game.submit(...)` 又 `return` 同一个着法——那会走两步。
- 不要睡超过 3 秒；每步限时含全部重试。
- `agents/examples/http_client_agent.py` 演示了跨进程接入（AI 跑在另一个进程/机器上）。
