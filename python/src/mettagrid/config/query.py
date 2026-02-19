"""Query types for spatial object-set operations.

Queries find sets of objects by tag or transitive closure.
MaterializedQuery uses a query to compute tag membership.

NOTE: AnyFilter is imported under TYPE_CHECKING to avoid circular imports
(filter → tag → query → filter). The models are rebuilt in
filter/__init__.py after all types are defined.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal, Optional, Union

from pydantic import Discriminator, Field

from mettagrid.base_config import Config
from mettagrid.config.tag import Tag

if TYPE_CHECKING:
    from mettagrid.config.filter.filter import AnyFilter


class Query(Config):
    """Find objects by tag with optional filters."""

    query_type: Literal["query"] = "query"
    tag: str = Field(description="Tag name for spatial lookup via TagIndex")
    filters: list["AnyFilter"] = Field(
        default_factory=list,
        description="Filters that matched objects must pass (all must match)",
    )
    max_items: Optional[int] = Field(default=None, description="Max objects to return (None = unlimited)")
    order_by: Optional[Literal["random"]] = Field(default=None, description="Order results before applying max_items")


class MaterializedQuery(Query):
    """A query whose results are materialized as a tag.

    Computed at init time, recomputed explicitly via RecomputeMaterializedQueryMutation.
    Defined in GameConfig.tags alongside plain Tags.
    """

    query_type: Literal["materialized"] = "materialized"
    query: "AnyQuery" = Field(description="Query that determines which objects get this tag")


class ClosureQuery(Query):
    """BFS from source through bridges. Expands source set transitively.

    Starting from objects matching `source`, expands through neighbors that
    pass the `bridge` filters within `radius` Chebyshev distance. All reachable
    objects (roots + bridges) are included, then filtered by `filters` if set.
    """

    query_type: Literal["closure"] = "closure"
    tag: str = Field(default="", description="Unused for closure queries (lookup is via source BFS)")
    source: "AnyQuery" = Field(description="Root objects to start BFS from")
    bridge: list["AnyFilter"] = Field(description="Filters applied to neighbors for bridge expansion")
    radius: int = Field(default=1, description="Chebyshev expansion distance")


AnyQuery = Annotated[Union[Query, MaterializedQuery, ClosureQuery], Discriminator("query_type")]


def query(tag: str | Tag, filters: list[AnyFilter] | None = None) -> Query:
    """Create a Query for finding objects by tag with optional filters.

    Examples:
        query("type:junction")
        query("type:agent", [hasTag(tag("collective:cogs"))])
    """
    tag_name = tag if isinstance(tag, str) else tag.name
    return Query(tag=tag_name, filters=filters or [])


def materializedQuery(tag: str | Tag, q: "AnyQuery") -> MaterializedQuery:
    """Create a MaterializedQuery that materializes query results as a tag."""
    tag_name = tag if isinstance(tag, str) else tag.name
    return MaterializedQuery(tag=tag_name, query=q)
