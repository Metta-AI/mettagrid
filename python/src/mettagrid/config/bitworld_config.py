"""BitWorld game engine environment configuration."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict

from mettagrid.config.env_config import EnvConfig


class BitWorldEnvConfig(EnvConfig):
    """First-class config for BitWorld game episodes.

    Unlike MettaGridConfig, BitWorld does not use map builders, grid objects,
    or observation configs.  Only ``game_name``, ``num_players``, ``seed``,
    ``max_ticks``, and ``connect_timeout_s`` are shared across all BitWorld
    games.  Game-specific server config (e.g. ``imposterCount`` for AmongThem,
    ``puzzleCount`` for Persephone's Escape) flows through ``server_config``.
    """

    model_config = ConfigDict(extra="forbid")

    game_engine: Literal["bitworld"] = "bitworld"
    game_name: str = "among_them"
    label: str = "bitworld_among_them"
    seed: int = 0
    max_ticks: int = 10000
    num_players: int = 5
    connect_timeout_s: float = 10.0
    server_config: dict[str, Any] = {}

    @property
    def num_agents(self) -> int:
        return self.num_players

    @property
    def manages_own_policies(self) -> bool:
        return True

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
