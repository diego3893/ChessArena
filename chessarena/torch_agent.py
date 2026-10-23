"""可选PyTorch生命周期适配；张量编码、解码和合法性完全由学生实现。"""

from .core.agent import Agent
from .core.errors import AgentLoadError


class TorchAgent(Agent):
    """实现load_model、encode、decode三个钩子，不限制模型输入输出形状。"""

    device = "cpu"
    warmup = True

    def __init__(self):
        super().__init__()
        self._model = None
        self._torch = None

    def load_model(self):
        """学生重建网络并加载权重，返回torch.nn.Module。"""
        raise NotImplementedError

    def encode(self, state):
        """学生自定义编码，返回模型输入；由学生放到self.device。"""
        raise NotImplementedError

    def predict(self, encoded):
        """多参数模型可覆盖本方法，例如self._model(**encoded)。"""
        return self._model(encoded)

    def decode(self, output, state):
        """学生自行判合法并解码成UCI字符串；平台不提供候选动作。"""
        raise NotImplementedError

    def prepare(self, state=None):
        """开局时加载/预热，避免把磁盘读取和首次推理计入每步时间。"""
        if self._model is not None:
            return
        try:
            import torch
        except ImportError as exc:
            raise AgentLoadError("PyTorch未安装，请执行pip install -r requirements-pytorch.txt") from exc
        try:
            self._torch = torch
            model = self.load_model()
            if not isinstance(model, torch.nn.Module):
                raise TypeError("load_model()须返回torch.nn.Module")
            self._model = model.to(self.device).eval()
            if self.warmup and state is not None:
                with torch.inference_mode():
                    self.predict(self.encode(state))
        except Exception as exc:
            self._model = None
            raise AgentLoadError("%s模型初始化失败：%s" % (self.name, exc)) from exc

    def on_game_start(self, state, color):
        self.prepare(state)

    def decide(self, state):
        """同一套推理可用于训练评估、平台比赛或独立HTTP客户端。"""
        self.prepare(state)
        with self._torch.inference_mode():
            output = self.predict(self.encode(state))
            return self.decode(output, state)

    def choose_move(self, state):
        if self.game is None:
            raise RuntimeError("未绑定棋局；独立推理请调用decide(state)")
        move = self.decide(state)
        return self.game.submit(move) if move is not None else None

    def close(self):
        self._model = None
        self._torch = None
