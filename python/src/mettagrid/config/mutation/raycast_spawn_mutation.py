"""RaycastSpawnMutation — spawn objects along rays from an entity."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal

from pydantic import Field

from mettagrid.base_config import Config

if TYPE_CHECKING:
    from mettagrid.config.filter import AnyFilter
    from mettagrid.config.game_value import AnyGameValue


class RaycastSpawnMutation(Config):
    """Spawn objects at empty cells along rays from the target entity.

    Walks each specified direction from the mutation target (ctx.target) up to
    max_range cells. At each empty cell, spawns an object of the given type.
    Stops the ray at blockers (objects matching any blocker filter).

    Example:
        RaycastSpawnMutation(
            object_type="explosion",
            directions=["north", "south", "east", "west"],
            max_range=2,
            blocker=[isA("wall"), isA("crate")],
        )
    """

    mutation_type: Literal["raycast_spawn"] = "raycast_spawn"
    object_type: str = Field(description="Object type to spawn at empty cells along the ray")
    directions: list[str] = Field(
        default_factory=lambda: ["north", "south", "east", "west"],
        description="Cardinal directions to walk",
    )
    max_range: "int | AnyGameValue" = Field(
        default=2, description="Maximum cells along each ray. Accepts int or GameValue."
    )
    blocker: Sequence["AnyFilter"] = Field(
        default_factory=list,
        description="Filters identifying objects that stop the ray",
    )
