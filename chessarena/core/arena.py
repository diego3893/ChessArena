"""``Arena``：环境装配。

负责读配置、把选手写法解析成 ``Agent``、创建对局。UI / 联赛在后续阶段接进来，
但"开一局"这件事从这里开始就只有一条路径。
"""

from pathlib import Path

from .agent import load_agent, resolve_player
from .game import START_FEN, Game

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
        logger=None,
    ):
        self.live = bool(live)
        self.record = bool(record)
        self.seed = 0 if seed is None else int(seed)
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
        self._games: list[Game] = []

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
        white_agent = resolve_player(white, seed=self.seed) if white is not None else None
        black_agent = resolve_player(black, seed=self.seed) if black is not None else None
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
        self._games.append(game)
        return game

    @property
    def games(self) -> tuple[Game, ...]:
        return tuple(self._games)

    def builtins(self) -> list[str]:
        """已实现的内置对手（阶段 1 只有 L1/L2）。"""
        from .builtin import available

        return available()

    def agents(self):
        """扫描 ``agents/`` 目录（阶段 6 实现）。"""
        return []

    def load_agent(self, path):
        return load_agent(path, seed=self.seed)

    def league(self, players, *, rounds=2, openings=8, max_concurrent=4):
        raise NotImplementedError("联赛在阶段 5 实现")

    def close(self):
        """释放对局里所有 AI（含外部引擎）。"""
        for game in self._games:
            for agent in (game.white, game.black):
                if agent is not None:
                    try:
                        agent.close()
                    except Exception as exc:  # 关闭失败不应影响退出
                        if self.logger:
                            self.logger("关闭 AI 失败：%r" % (exc,))
        self._games.clear()
