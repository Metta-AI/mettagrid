"""Max distance filter configuration and helper functions."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from mettagrid.config.filter.filter import Filter, HandlerTarget
from mettagrid.config.query import AnyQuery


class MaxDistanceFilter(Filter):
    """Filter that checks L2 distance (sum of squares, no sqrt).

    radius=0 means unlimited (no distance constraint; always passes).

    Two modes:
    - **Unary** (query is set): passes if target is within radius of any
      object matching the query. With radius=0, passes if the query returns
      any results (distance unchecked). Used in event/handler filters.
    - **Binary** (query is None): passes if L2 distance from actor to
      target <= radius, or unconditionally when radius=0. Source comes from
      HandlerContext.actor. Used in ClosureQuery edge_filters.

    Comparison: dr*dr + dc*dc <= radius*radius

    Examples:
        isNear(typeTag("junction"), radius=2)   # unary
        maxDistance(10)                           # binary, 10-cell limit
        maxDistance(0)                            # binary, unlimited range
    """

    filter_type: Literal["max_distance"] = "max_distance"
    target: HandlerTarget = Field(
        default=HandlerTarget.TARGET,
        description="Entity to check the filter against",
    )
    query: Optional["AnyQuery"] = Field(
        default=None,
        description="Query to find nearby objects (None = binary mode)",
    )
    radius: int = Field(
        default=1,
        description="L2 distance radius to check (compared as sum of squares). 0 means unlimited.",
    )


# ===== Helper Filter Functions =====


def maxDistance(radius: int) -> MaxDistanceFilter:
    """Binary filter: L2 distance from source to target must be <= radius.

    radius=0 means unlimited (always passes, no distance constraint).
    Used in ClosureQuery edge_filters where source=net_member, target=candidate.
    """
    return MaxDistanceFilter(target=HandlerTarget.TARGET, radius=radius)


def isNear(query: "str | AnyQuery", radius: int = 1) -> MaxDistanceFilter:
    """Unary filter: target is within radius of an object matching the query.

    Accepts a tag string or a Query. Strings are auto-wrapped into Query(source=str).

    Examples:
        isNear(typeTag("junction"), radius=3)
        isNear(query(typeTag("agent"), [hasTag("collective:cogs")]))
    """
    from mettagrid.config.query import Query  # noqa: PLC0415

    if isinstance(query, str):
        query = Query(source=query)
    return MaxDistanceFilter(target=HandlerTarget.TARGET, query=query, radius=radius)
