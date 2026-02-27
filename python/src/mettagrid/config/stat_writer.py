from __future__ import annotations

from mettagrid.base_config import Config
from mettagrid.config.game_value import AnyGameValue


class StatWriter(Config):
    name: str
    value: AnyGameValue
    accumulate: bool = False
