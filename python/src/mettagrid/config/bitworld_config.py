"""BitWorld game engine environment configuration."""

from __future__ import annotations

from typing import Any, Literal

from mettagrid.config.env_config import EnvConfig


class BitWorldEnvConfig(EnvConfig):
    """First-class config for BitWorld game episodes.

    Unlike MettaGridConfig, BitWorld does not use map builders, grid objects,
    or observation configs.  All BitWorld-specific fields live here rather
    than polluting :class:`~mettagrid.config.mettagrid_config.GameConfig`.
    """

    game_engine: Literal["bitworld"] = "bitworld"
    game_name: str = "among_them"
    label: str = "bitworld_among_them"
    seed: int = 0
    max_ticks: int = 10000
    num_players: int = 5
    imposter_count: int = 1
    tasks_per_player: int = 8
    task_complete_ticks: int | None = None
    imposter_cooldown_ticks: int = 1200
    vote_timer_ticks: int = 600
    connect_timeout_s: float = 10.0

    @property
    def num_agents(self) -> int:
        return self.num_players

    @staticmethod
    def set_map_seed(config: dict[str, Any], seed: int) -> None:
        config["seed"] = seed

    @staticmethod
    def set_max_steps(config: dict[str, Any], max_steps: int) -> None:
        config["max_ticks"] = max_steps

    @staticmethod
    def get_max_steps(config: dict[str, Any]) -> int:
        return config["max_ticks"]

    @staticmethod
    def get_num_agents(config: dict[str, Any]) -> int:
        return config["num_players"]
