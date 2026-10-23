"""``Arena``：环境装配。

负责读配置、把选手写法解析成 ``Agent``、创建对局。UI / 联赛在后续阶段接进来，
但"开一局"这件事从这里开始就只有一条路径。
"""

from pathlib import Path

from .agent import load_agent, resolve_player
from .game import START_FEN, Game
from .recorder import Recorder

DEFAULTS = {
    "server": {"host": "127.0.0.1", "port": 8000},
    "game": {
        "timeout": 3.0,
        "max_retries": 3,
        "on_retry_exhausted": "forfeit",
        "on_timeout": "forfeit",
    },
    "league": {"rounds": 2, "openings": 8, "max_concurrent": 4},
    "builtin": ["random", "greedy", "minimax2", "minimax3", "stockfish"],
}


def _deep_merge(base, extra):
    out = dict(base)
    for key, value in (extra or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path="config.yaml"):
    """读 ``config.yaml``；文件不存在就用默认值。"""
    p = Path(path)
    if not p.exists():
        return dict(DEFAULTS)
    try:
        import yaml
    except ImportError:  # pragma: no cover - yaml 是本项目的硬依赖之一
        return dict(DEFAULTS)
    with p.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return _deep_merge(DEFAULTS, data)


class Arena:
    """环境装配器。"""

    def __init__(
        self,
        *,
        live=True,
        record=False,
        seed=0,
        config="config.yaml",
        timeout=None,
        max_retries=None,
        on_retry_exhausted=None,
        on_timeout=None,
        runs_dir="runs",
        agents_dir="agents",
        logger=None,
    ):
        self.live = bool(live)
        self.record = bool(record)
        self.seed = 0 if seed is None else int(seed)
        self.runs_dir = Path(runs_dir)
        self.agents_dir = Path(agents_dir)
        self.agent_errors: list = []
        self.config = load_config(config)
        game_cfg = self.config.get("game", {})
        self.timeout = float(timeout if timeout is not None else game_cfg.get("timeout", 3.0))
        self.max_retries = int(
            max_retries if max_retries is not None else game_cfg.get("max_retries", 3)
        )
        self.on_retry_exhausted = (
            on_retry_exhausted
            if on_retry_exhausted is not None
            else game_cfg.get("on_retry_exhausted", "forfeit")
        )
        self.on_timeout = (
            on_timeout if on_timeout is not None else game_cfg.get("on_timeout", "forfeit")
        )
        self.logger = logger
        self.stockfish = dict(self.config.get("stockfish") or {})
        self._games: list[Game] = []
        self._recorders: list[Recorder] = []

    # ------------------------------------------------------------------
    def new_game(
        self,
        *,
        white,
        black,
        fen=None,
        timeout=None,
        max_retries=None,
        game_id=None,
    ) -> Game:
        """开一局。``white`` / ``black`` 见《API总表》§10。"""
        white_agent = (resolve_player(white, seed=self.seed, stockfish=self.stockfish)
                       if white is not None else None)
        black_agent = (resolve_player(black, seed=self.seed, stockfish=self.stockfish)
                       if black is not None else None)
        try:
            game = Game(
                white_agent,
                black_agent,
                fen=fen or START_FEN,
                timeout=self.timeout if timeout is None else float(timeout),
                max_retries=self.max_retries if max_retries is None else int(max_retries),
                on_retry_exhausted=self.on_retry_exhausted,
                on_timeout=self.on_timeout,
                game_id=game_id,
                live=self.live,
                record=self.record,
                seed=self.seed,
                logger=self.logger,
            )
        except Exception:
            for agent in (white_agent, black_agent):
                if agent is not None:
                    try:
                        agent.close()
                    except Exception:
                        pass
            raise
        self._games.append(game)
        if self.record:
            path = self.runs_dir / ("%s.jsonl" % (game.game_id,))
            self._recorders.append(Recorder(path, game=game))
        return game

    @property
    def games(self) -> tuple[Game, ...]:
        return tuple(self._games)

    def builtins(self) -> list[str]:
        """已注册的内置对手（L1–L5）。"""
        from ..builtin import available

        return available()

    def agents(self):
        """扫描 ``agents/*.py``，返回可下拉的选手列表。

        导入失败的文件不会拖垮页面：跳过并记在 ``self.agent_errors`` 里。
        """
        from .agent import AgentInfo, scan_agents

        infos = []
        self.agent_errors = []
        for info, error in scan_agents(self.agents_dir, seed=self.seed):
            if error is not None:
                self.agent_errors.append((str(info), error))
                continue
            infos.append(info)
        return infos

    def load_agent(self, path):
        return load_agent(path, seed=self.seed)

    def league(self, players, *, rounds=2, openings=8, max_concurrent=4, **kwargs):
        from ..league import League

        return League(
            players,
            rounds=rounds,
            openings=openings,
            max_concurrent=max_concurrent,
            seed=self.seed,
            **kwargs,
        )

    def close(self):
        """释放对局里所有 AI（含外部引擎）与录像文件。"""
        for recorder in self._recorders:
            recorder.close()
        self._recorders.clear()
        for game in self._games:
            for agent in (game.white, game.black):
                if agent is not None:
                    try:
                        agent.close()
                    except Exception as exc:  # 关闭失败不应影响退出
                        if self.logger:
                            self.logger("关闭 AI 失败：%r" % (exc,))
        self._games.clear()
