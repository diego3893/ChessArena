"""``Agent`` 基类、人类玩家与选手解析。

学生只需要继承 ``Agent`` 并实现 ``choose_move``。平台在每一步调用它，
把返回值交给 ``Game.submit()``；也可以用它注入的 ``self.game`` 自己落子（层 2）。
"""

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

from .errors import AgentLoadError


@dataclass(frozen=True, slots=True)
class AgentInfo:
    """``agents/`` 目录里扫到的一个学生 AI。"""

    name: str
    path: str        # 相对项目根，如 agents/my_agent.py
    class_name: str
    spec: str        # 可直接传给 white= / black=

    def __str__(self):
        return self.spec


class Agent:
    """AI 基类。"""

    #: 显示在界面/日志里的名字
    name = "未命名"
    #: 内置档位可置 True：跳过"可中断线程"，换取更高吞吐
    fast_local = False
    #: 人类玩家：被拒不消耗重试次数（手滑是常态）
    is_human = False

    def __init__(self):
        # 平台在开局时注入：当前对局、执子颜色、随机数种子
        self.game = None
        self.color = None
        self.seed = 0

    def choose_move(self, state):
        """返回一个 UCI 着法（``"e2e4"``）或 ``None``（视为弃权）。"""
        raise NotImplementedError

    # --- 以下钩子都是可选的 -------------------------------------------
    def on_game_start(self, state, color):
        pass

    def on_game_end(self, result):
        pass

    def on_opponent_move(self, move):
        pass

    def close(self):
        pass

    def __repr__(self):
        return "%s(name=%r)" % (type(self).__name__, self.name)


class HumanAgent(Agent):
    """人类玩家：在终端读一行 UCI 着法。"""

    name = "人类"
    fast_local = True
    is_human = True

    def __init__(self, prompt="你的着法"):
        super().__init__()
        self.prompt = prompt

    def choose_move(self, state):
        print(state.pretty())
        while True:
            try:
                raw = input("%s（UCI，如 e2e4；输入 resign 认输）> " % self.prompt)
            except (EOFError, KeyboardInterrupt):
                print()
                return None
            text = raw.strip()
            if not text:
                continue
            if text.lower() in ("resign", "quit", "exit"):
                return None
            return text


def load_agent(path, *, seed=0):
    """按文件路径导入 ``Agent`` 子类（``agents/my_agent.py``）。"""
    p = Path(path)
    if not p.exists():
        raise AgentLoadError("找不到 AI 文件：%s" % (p,))
    mod_name = "chessarena_agents_%s" % (p.stem,)
    spec = importlib.util.spec_from_file_location(mod_name, p)
    if spec is None or spec.loader is None:
        raise AgentLoadError("无法加载 AI 文件：%s" % (p,))
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # 学生代码的导入错误要变成可读信息
        raise AgentLoadError("导入 %s 失败：%s" % (p.name, exc)) from exc

    candidates = [
        obj
        for obj in vars(module).values()
        if isinstance(obj, type) and issubclass(obj, Agent) and obj is not Agent
    ]
    if not candidates:
        raise AgentLoadError("%s 里没有 Agent 子类" % (p.name,))
    # 约定：优先用文件里最后定义的那个类（通常是学生自己写的）
    cls = candidates[-1]
    agent = cls()
    agent.seed = seed
    return agent


def scan_agents(directory, *, seed=0):
    """扫描目录下所有 ``*.py``，产出 ``(AgentInfo, error)``。

    导入失败只记为错误，不抛出——页面下拉框要能列出其余可用的 AI。
    """
    base = Path(directory)
    results = []
    if base.is_dir():
        for path in sorted(base.glob("*.py")):
            if path.name.startswith("_"):
                continue
            rel = path.as_posix()
            try:
                agent = load_agent(rel, seed=seed)
            except Exception as exc:  # 学生代码导入出错
                results.append((rel, exc))
                continue
            info = AgentInfo(
                name=getattr(agent, "name", type(agent).__name__),
                path=rel,
                class_name=type(agent).__name__,
                spec=rel,
            )
            try:
                agent.close()
            except Exception:
                pass
            results.append((info, None))

    # 外部的 UCI / HTTP 对手（agents/agents.json）
    from .external import load_registry

    try:
        entries = load_registry((base / "agents.json").as_posix()
                                if base.is_dir() else "agents/agents.json")
    except Exception as exc:
        results.append(("agents/agents.json", exc))
        entries = []
    for item in entries:
        spec = "%s:%s" % (item["type"], item["name"])
        results.append((AgentInfo(
            name=item["name"], path="agents/agents.json",
            class_name="UciAgent" if item["type"] == "uci" else "HttpAgent",
            spec=spec,
        ), None))
    return results


def resolve_player(spec, *, seed=0):
    """把 ``white=`` / ``black=`` 的写法解析成 ``Agent`` 实例。"""
    if isinstance(spec, Agent):
        spec.seed = getattr(spec, "seed", 0) or seed
        return spec

    if not isinstance(spec, str):
        raise AgentLoadError("不认识的选手写法：%r（要 Agent 实例或字符串）" % (spec,))

    text = spec.strip()
    low = text.lower()

    if low == "human":
        return HumanAgent()

    if low.startswith("builtin:"):
        from ..builtin import make_builtin

        try:
            return make_builtin(low.split(":", 1)[1], seed=seed)
        except KeyError as exc:
            raise AgentLoadError(str(exc)) from exc

    if low.startswith(("uci:", "http:")):
        from .external import resolve_external

        return resolve_external(spec, seed=seed)

    if text.endswith(".py"):
        return load_agent(text, seed=seed)

    raise AgentLoadError("不认识的选手写法：%r（见《API总表》§10）" % (spec,))
