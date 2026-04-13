"""Raycast query — ray-casting that generates objects on unblocked rays.

Walks rays from source objects in specified directions and returns all
objects encountered on each ray before (and optionally including) the
first blocker. Defaults to 4 cardinal directions (N/S/E/W).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal, Optional

from pydantic import Field

from mettagrid.base_config import Config

if TYPE_CHECKING:
    from mettagrid.config.filter import AnyFilter
    from mettagrid.config.game_value import AnyGameValue
    from mettagrid.config.query import AnyQuery


class RaycastQuery(Config):
    """Query that walks rays from source objects in specified directions.

    Walks each direction from each source object up to max_range cells.
    At each cell, if there's an object, checks it against blocker filters.
    Blockers stop the ray (and are optionally included in results).
    Non-blockers are included and the ray continues.

    Example:
        RaycastQuery(
            source=query(typeTag("bomb"), [isNot(targetHas({"fuse": 1}))]),
            max_range=2,
            blocker=[isA("wall"), isA("crate")],
            include_blocker=True,
        )
    """

    query_type: Literal["raycast"] = "raycast"
    source: "str | AnyQuery" = Field(description="Query to find ray origin objects")
    max_range: "int | AnyGameValue" = Field(
        default=2, description="Maximum cells along each ray. Accepts int or GameValue."
    )
    directions: list[str] = Field(
        default_factory=lambda: ["north", "south", "east", "west"],
        description="Ray directions (default: 4 cardinal)",
    )
    blocker: Sequence["AnyFilter"] = Field(
        default_factory=list,
        description="Filters identifying objects that stop the ray",
    )
    include_blocker: bool = Field(
        default=True,
        description="Whether the first blocker on each ray is included in results",
    )
    max_items: "Optional[int | AnyGameValue]" = Field(
        default=None, description="Max objects to return (None = unlimited). Accepts int or GameValue."
    )
    order_by: Optional[Literal["random"]] = Field(default=None, description="Order results before applying max_items")


def raycastQuery(
    source: "str | AnyQuery",
    max_range: "int | AnyGameValue" = 2,
    directions: list[str] | None = None,
    blocker: "Sequence[AnyFilter] | None" = None,
    include_blocker: bool = True,
) -> RaycastQuery:
    """Create a RaycastQuery for ray-casting from source objects.

    Args:
        source: Query to find ray origin objects (e.g., exploding bombs)
        max_range: Maximum cells along each ray
        directions: Ray directions (default: 4 cardinal)
        blocker: Filters that identify blocking objects (walls, crates, etc.)
        include_blocker: Whether the first blocker itself is included in results

    Examples:
        raycastQuery(source=query(typeTag("bomb")), max_range=2, blocker=[isA("wall")])
        raycastQuery(source=..., directions=["north", "east"])  # only 2 arms
    """
    return RaycastQuery(
        source=source,
        max_range=max_range,
        directions=directions or ["north", "south", "east", "west"],
        blocker=list(blocker) if blocker else [],
        include_blocker=include_blocker,
    )
