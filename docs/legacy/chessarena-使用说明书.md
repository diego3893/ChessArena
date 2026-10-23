# ChessArena使用说明

## 1 启动

```bash
pip install -r requirements.txt
python -m chessarena serve
```

打开http://127.0.0.1:8000/。Windows可运行start.bat。界面使用chessground，无前端构建步骤。

## 2 对局

顶部选择白方和黑方，点击开局。人类对内置AI为人机；两个AI为机机观战；外部AI/API选手等待独立程序提交。内置五档含random、greedy、minimax2、minimax3和Stockfish。Stockfish默认2600、每步思考1秒，可在config.yaml调整。

人类通过点击或拖拽提出着法，裁判检查后才改变真实局面；非法动作回退。界面不提供合法落点列表。到达底线的兵可选择升变种类，再由裁判判断是否合法。

支持翻转、记谱、吃子显示、悔棋、认输、PGN导出、复制FEN，以及机机暂停、单步和调速。心跳与HTTP校准负责同步，快照revision支持悔棋回退。

## 3 学生模型

```bash
pip install -r requirements-pytorch.txt
python agents/examples/train_torch_demo.py --steps 20
python -m chessarena serve --white agents/A.py --black agents/B.py
```

A/B是接入演示，短训权重不代表棋力。学生将自己的入口和资源放在agents/，自行实现编码、网络、合法性判断、解码和权重加载。平台统一State/Player接口和最终裁判。详见[学生API](chessarena-学生API.md)与[模型提交规范](chessarena-模型提交规范.md)。

## 4 独立训练与评测

```bash
python -m chessarena test agents/A.py --vs agents/B.py --games 2
python -m chessarena league --players agents/A.py,agents/B.py --rounds 1 --concurrent 1
```

训练用live=False，学生收到的仍是只读局面；没有合法动作列表、动作掩码或平台推演方法。合法性错误以返回码报告，默认按同一步预算重试。

独立进程可用Client连接api选手，通过GET /state和POST /move操作；使用统一计时的课程比赛应走Agent等平台驱动接入。

## 5 排查

AI不走时检查页面状态和GET /debug。模型首次加载发生在开局，读盘和预热不计入每步预算。权重缺失、网络结构不匹配或编码版本错误由学生入口报告。

旧legal_moves/State.apply接口已在v2删除，需升级学生脚本。棋盘与历史信息仍完整提供。基础平台无需PyTorch；只有神经网络选手需要可选依赖。
