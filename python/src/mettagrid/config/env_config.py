"""Base environment config for all game engines."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from mettagrid.base_config import Config


class EnvConfig(Config):
    """Base class for all game engine environment configurations.

    Subclasses must set ``game_engine`` to a ``Literal`` with a default value
    and implement the ``num_agents`` property and ``set_map_seed`` method.
    """

    game_engine: str

    @property
    @abstractmethod
    def num_agents(self) -> int: ...

    @staticmethod
    @abstractmethod
    def set_map_seed(config: dict[str, Any], seed: int) -> None:
        """Set the map/game seed on a raw config dict *in place*.

        Operates on raw dicts so that legacy JSONB fields not modeled by
        the current Pydantic schema are preserved across round-trips.
        """
        ...

    @staticmethod
    @abstractmethod
    def set_max_steps(config: dict[str, Any], max_steps: int) -> None:
        """Set the max steps/ticks on a raw config dict *in place*."""
        ...

    @staticmethod
    @abstractmethod
    def get_max_steps(config: dict[str, Any]) -> int:
        """Read the max steps/ticks from a raw config dict."""
        ...

    @staticmethod
    @abstractmethod
    def get_num_agents(config: dict[str, Any]) -> int:
        """Read the agent count from a raw config dict."""
        ...
