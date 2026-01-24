"""Near filter configuration and helper functions."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from mettagrid.config.filter.filter import AnyFilter, Filter, HandlerTarget


class NearFilter(Filter):
    """Filter that checks if target is within radius of an object matching inner filters.

    This is useful for proximity-based mechanics. The filter passes if:
    - Target is within the specified radius of an object that passes ALL inner filters

    Examples:
        isNear("type:junction", radius=3)  # Near junctions
        isNear("type:clips")  # Near clips objects
    """

    filter_type: Literal["near"] = "near"
    tag: str = Field(description="Tag name to identify nearby candidate objects")
    filters: list[AnyFilter] = Field(
        default_factory=list,
        description="Additional filters that nearby objects must pass (all must match)",
    )
    radius: int = Field(default=1, description="Chebyshev distance (square radius) to check")


# ===== Helper Filter Functions =====


def isNear(tag: str, radius: int = 1, filters: list[AnyFilter] | None = None) -> NearFilter:
    """Filter: target is within radius of an object with the given tag.

    This is useful for proximity-based mechanics. The filter passes if:
    - Target is within radius tiles of an object with the tag (and passing filters)

    Examples:
        isNear("type:junction", radius=3)  # Near junctions
        isNear("type:clips")  # Near clips objects

    Args:
        tag: Tag name to identify nearby candidate objects
        radius: Chebyshev distance (square radius) to check
        filters: Additional filters that nearby objects must pass
    """
    return NearFilter(target=HandlerTarget.TARGET, tag=tag, filters=filters or [], radius=radius)
