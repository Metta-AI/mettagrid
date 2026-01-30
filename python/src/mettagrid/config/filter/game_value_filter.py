"""Game value filter configuration."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from mettagrid.config.filter.filter import Filter
from mettagrid.config.game_value import AnyGameValue


class GameValueFilter(Filter):
    """Filter that checks if a game value meets a minimum threshold."""

    filter_type: Literal["game_value"] = "game_value"
    value: AnyGameValue
    min: int = Field(default=0, description="Minimum value required")
