"""Game value mutation configuration."""

from __future__ import annotations

from typing import Literal, Union

from pydantic import Field

from mettagrid.config.game_value import InventoryValue, StatValue
from mettagrid.config.mutation.mutation import EntityTarget, Mutation


class SetGameValueMutation(Mutation):
    """Apply a delta to an inventory or stat value."""

    mutation_type: Literal["set_game_value"] = "set_game_value"
    value: Union[InventoryValue, StatValue]
    delta: int = Field(description="Delta to apply")
    target: EntityTarget = Field(default=EntityTarget.ACTOR, description="Entity to apply to")
