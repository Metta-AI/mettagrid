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

if TYPE_CHECKING:
    from mettagrid.config.filter.filter import AnyFilter


class Query(Config):
    """Find objects by tag with optional filters."""

    query_type: Literal["query"] = "query"
    source: "str | AnyQuery" = Field(description="Tag name or sub-query for spatial lookup via TagIndex")
    filters: list["AnyFilter"] = Field(
        default_factory=list,
        description="Filters that matched objects must pass (all must match)",
    )
    max_items: Optional[int] = Field(default=None, description="Max objects to return (None = unlimited)")
    order_by: Optional[Literal["random"]] = Field(default=None, description="Order results before applying max_items")


class MaterializedQuery(Query):
    """A query whose results are materialized as a tag.

    Computed at init time, recomputed explicitly via RecomputeMaterializedQueryMutation.
    Defined in GameConfig.materialize_queries.

    The output tag may overlap with existing static tags — this is intentional.
    It allows materialized queries to enrich objects that already carry the tag
    (e.g. adding a computed "type:hub" to dynamically-discovered network members).
    """

    query_type: Literal["materialized"] = "materialized"
    source: str = Field(default="", description="Unused for materialized queries")
    tag: str = Field(description="Output tag name that matched objects receive")
    query: "AnyQuery" = Field(description="Query that determines which objects get this tag")


class ClosureQuery(Query):
    """BFS from source through bridges. Expands source set transitively.

    Starting from objects matching `source`, expands through neighbors that
    pass the `bridge` filters within `radius` Chebyshev distance. All reachable
    objects (roots + bridges) are included, then filtered by `filters` if set.
    """

    query_type: Literal["closure"] = "closure"
    bridge: list["AnyFilter"] = Field(description="Filters applied to neighbors for bridge expansion")
    radius: int = Field(default=1, description="Chebyshev expansion distance")


AnyQuery = Annotated[Union[Query, MaterializedQuery, ClosureQuery], Discriminator("query_type")]


def query(source: "str | AnyQuery", filters: AnyFilter | list[AnyFilter] | None = None) -> Query:
    """Create a Query for finding objects by tag with optional filters.

    Examples:
        query(typeTag("junction"))
        query(typeTag("agent"), [hasTag("collective:cogs")])
    """
    return Query(source=source, filters=filters if isinstance(filters, list) else [filters] if filters else [])


def materializedQuery(tag: str, q: "AnyQuery") -> MaterializedQuery:
    """Create a MaterializedQuery that materializes query results as a tag."""
    return MaterializedQuery(tag=tag, query=q)
