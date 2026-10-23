"""学生B的模型入口；模型结构和权重可以与A不同。"""

from pathlib import Path

from agents.examples._torch_student import ExampleStudent


class ModelB(ExampleStudent):
    name = "学生示例B"
    weights = Path(__file__).resolve().parent / "weights" / "B.pt"
