# 模型提交规范

## 1 分工

平台提供完整只读局面、比赛调度、时间/重试管理和最终裁判。学生提供网络定义、训练权重、编码器、合法性判断、解码器及Agent入口。不同模型的输入输出维度可以不同，无全班共用的编码器、动作编号或动作掩码。

## 2 推荐提交目录

```text
agents/
  A.py                   # 学生A入口
  B.py                   # 学生B入口
  submissions/
    a/                   # A自己的网络、编码器和解码器
    b/                   # B自己的网络、编码器和解码器
  weights/
    A.pt
    B.pt
```

平台只扫描agents/第一层的*.py；辅助代码放子目录或以下划线开头。入口里定义一个Agent或TorchAgent子类，name用于页面显示；权重使用相对入口的绝对解析路径，例如Path(__file__).resolve().parent / "weights" / "A.pt"。

PyTorch权重建议保存state_dict，学生自己维护网络结构、输入输出含义、编码版本和加载代码。平台不从权重文件猜测结构。A和B可使用不同实现和独立权重。

## 3 PyTorch参考示例

```bash
pip install -r requirements-pytorch.txt
python agents/examples/train_torch_demo.py --steps 20
python -m chessarena serve --white agents/A.py --black agents/B.py
```

然后浏览器打开http://127.0.0.1:8000/。示例A、B会出现在模型下拉框中。

示例由agents/A.py、agents/B.py和agents/examples/_torch_student.py组成。编码器和解码器均位于学生目录；12个棋子通道与20480动作只属于该示例，其他学生完全可以采用不同表示。示例解码器自行导入python-chess筛选动作；若课程要求自己实现棋规，可替换这一段，平台无需修改。

短训脚本使用32个局面和随机合法动作标签，生成隐藏层分别为24和40的两个独立网络。**这些演示权重用于验证接入、训练保存与比赛闭环，不代表棋力或课程基线。**默认不覆盖已有权重；重新训练演示权重需指定新out目录或显式使用--force。

## 4 接口契约

TorchAgent由学生实现load_model()/encode(state)/decode(output, state)。load_model返回nn.Module，encode返回其输入，decode返回UCI字符串或None（弃权）。需要多个模型参数、字典输入或价值头时自行覆盖predict或在decode中处理，平台不约束内部形状。

平台负责开局加载、eval、推理模式与预热。一次比赛只加载一次模型，逐步推理不读盘。编码器负责设备和数据类型；模型由平台移到self.device。默认CPU，可在学生入口选择cuda，评测双方应遵守课程统一的硬件预算。

学生解码出动作后由TorchAgent调用self.game.submit。非法/格式错误会被拒绝并按统一预算重试；平台不会用随机动作掩盖学生模型的错误（除非助教显式配置了替走策略）。

训练、推理和比赛必须使用学生自己一致的编码/解码版本；建议在学生权重元信息里记录版本并在load_model时检查。平台只统一State和Player接口。

## 5 验收命令

```bash
python -m chessarena test agents/A.py --vs agents/B.py --games 2
python -m chessarena play --white agents/A.py --black agents/B.py --pgn runs/A-vs-B.pgn
python -m unittest tests.test_student_contract tests.test_torch_agent
```

正式评测交换黑白、统一每步时限及硬件条件。更多字段见[学生API](chessarena-学生API.md)。
