"""Max distance filter configuration and helper functions."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from mettagrid.config.filter.filter import Filter, HandlerTarget
from mettagrid.config.query import AnyQuery


class MaxDistanceFilter(Filter):
    """Filter that checks if target is within radius of an object matching a query.

    This is useful for proximity-based mechanics. The filter passes if:
    - Target is within the specified radius of an object that matches the query

    The query's tag is required for efficient spatial lookup via TagIndex. Candidate
    objects are found by tag, then query filters are applied to each candidate.

    Converted to MaxDistanceFilterConfig + TagQueryConfig in the C++ layer.

    Examples:
        isNear(query("junction", [hasTag(tag("collective:clips"))]), radius=2)
    """

    filter_type: Literal["max_distance"] = "max_distance"
    target: HandlerTarget = Field(
        default=HandlerTarget.TARGET,
        description="Entity to check the filter against",
    )
    query: "AnyQuery" = Field(description="Query to find nearby candidate objects")
    radius: int = Field(default=1, description="Chebyshev distance (square radius) to check")


# ===== Helper Filter Functions =====


def isNear(query: "AnyQuery", radius: int = 1) -> MaxDistanceFilter:
    """Filter: target is within radius of an object matching the query.

    This is useful for proximity-based mechanics. The filter passes if:
    - Target is within radius tiles of an object matching the query

    Args:
        query: Query identifying nearby objects (tag + optional filters)
        radius: Chebyshev distance (square radius) to check

    Examples:
        isNear(query(typeTag("junction"), [isAlignedTo("clips")]), radius=3)
        isNear(query(typeTag("agent"), [hasTag(tag("collective:cogs"))]))
    """
    return MaxDistanceFilter(target=HandlerTarget.TARGET, query=query, radius=radius)
