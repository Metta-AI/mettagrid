"""Game value mutation configuration."""

from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import Field, model_validator

from mettagrid.config.game_value import ConstValue, InventoryValue, StatValue
from mettagrid.config.mutation.mutation import EntityTarget, Mutation


class SetGameValueMutation(Mutation):
    """Apply a delta to an inventory or stat value.

    The delta comes from `source`. If `source` is not provided, `delta` is used as a constant.
    Exactly one of `source` or `delta` should be set.
    """

    mutation_type: Literal["set_game_value"] = "set_game_value"
    value: Union[InventoryValue, StatValue]
    delta: float = Field(default=0, description="Static delta (used when source is not provided)")
    target: EntityTarget = Field(default=EntityTarget.ACTOR, description="Entity to apply to")
    source: Optional[Union[InventoryValue, StatValue, ConstValue]] = Field(
        default=None, description="Dynamic source for the delta value"
    )

    @model_validator(mode="after")
    def _check_source_or_delta(self) -> "SetGameValueMutation":
        has_source = self.source is not None
        has_delta = self.delta != 0
        if has_source and has_delta:
            raise ValueError("Specify either 'source' or 'delta', not both")
        return self
