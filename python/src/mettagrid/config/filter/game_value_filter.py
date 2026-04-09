"""Game value filter configuration."""

from __future__ import annotations

from typing import Literal, Union

from pydantic import Field

from mettagrid.config.filter.filter import Filter
from mettagrid.config.game_value import AnyGameValue


class GameValueFilter(Filter):
    """Filter that checks if a game value meets a minimum threshold.

    The threshold can be a static int or a dynamic AnyGameValue expression
    that is resolved at runtime.
    """

    filter_type: Literal["game_value"] = "game_value"
    value: AnyGameValue
    min: Union[int, AnyGameValue] = Field(default=0, description="Minimum threshold (static int or dynamic game value)")
