"""Near filter configuration and helper functions."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from mettagrid.config.filter.filter import AnyFilter, Filter, HandlerTarget


class NearFilter(Filter):
    """Filter that checks if target is within radius of an object matching filters.

    This is useful for proximity-based mechanics. The filter passes if:
    - Target is within the specified radius of an object that passes ALL filters

    The target_tag is required for efficient spatial lookup via TagIndex. Candidate
    objects are found by tag, then filters are applied to each candidate.

    Examples:
        isNear("junction", [isAlignedTo("clips")], radius=2)
    """

    filter_type: Literal["near"] = "near"
    target: HandlerTarget = Field(
        default=HandlerTarget.TARGET,
        description="Entity to check the filter against",
    )
    target_tag: str = Field(description="Tag name to identify nearby candidate objects")
    filters: list[AnyFilter] = Field(
        default_factory=list,
        description="Filters that nearby objects must pass (all must match)",
    )
    radius: int = Field(default=1, description="Chebyshev distance (square radius) to check")


# ===== Helper Filter Functions =====


def isNear(tag: str, filters: list[AnyFilter] | None = None, radius: int = 1) -> NearFilter:
    """Filter: target is within radius of an object with the given tag.

    This is useful for proximity-based mechanics. The filter passes if:
    - Target is within radius tiles of an object with the tag (and passing filters)

    Args:
        tag: Tag for efficient spatial lookup (e.g., "type:junction")
        filters: Additional filters that nearby objects must pass
        radius: Chebyshev distance (square radius) to check

    Examples:
        isNear("type:junction", radius=3)  # Near junctions
        isNear("type:clips")  # Near clips objects
    """
    return NearFilter(target=HandlerTarget.TARGET, target_tag=tag, filters=filters or [], radius=radius)
