"""学生A的模型入口；可替换为学生自己提交的实现。"""

from pathlib import Path

from agents.examples._torch_student import ExampleStudent


class ModelA(ExampleStudent):
    name = "学生示例A"
    weights = Path(__file__).resolve().parent / "weights" / "A.pt"
