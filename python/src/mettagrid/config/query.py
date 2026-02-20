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


class ClosureQuery(Config):
    """BFS from source through candidates connected by edge filters.

    Evaluates ``source`` to get seed objects, ``candidates`` to get the
    candidate pool, then BFS-expands: for each frontier node, candidates
    passing all ``edge_filters`` (evaluated with source=frontier,
    target=candidate) are added to the net. Repeats until convergence.
    Final set is post-filtered by ``filters`` if set.

    Example::

        ClosureQuery(
            source=query(typeTag("hub"), [hasTag("collective:cogs")]),
            candidates=query(typeTag("junction"), [hasTag("collective:cogs")]),
            edge_filters=[maxDistance(10)],
        )
    """

    query_type: Literal["closure"] = "closure"
    source: "str | AnyQuery" = Field(description="Seed objects for BFS")
    candidates: "str | AnyQuery" = Field(description="Objects that can join the network")
    edge_filters: list["AnyFilter"] = Field(
        default_factory=list,
        description="Binary filters: (net_member, candidate) -> bool",
    )
    filters: list["AnyFilter"] = Field(
        default_factory=list,
        description="Unary filters applied to final result set",
    )
    max_items: Optional[int] = Field(default=None, description="Max objects to return (None = unlimited)")
    order_by: Optional[Literal["random"]] = Field(default=None, description="Order results before applying max_items")


AnyQuery = Annotated[Union[Query, MaterializedQuery, ClosureQuery], Discriminator("query_type")]


def query(source: "str | AnyQuery", filters: "AnyFilter | list[AnyFilter] | None" = None) -> Query:
    """Create a Query for finding objects by tag with optional filters.

    Examples:
        query(typeTag("junction"))
        query(typeTag("agent"), [hasTag("collective:cogs")])
    """
    return Query(source=source, filters=filters if isinstance(filters, list) else [filters] if filters else [])


def closureQuery(
    source: "str | AnyQuery",
    candidates: "str | AnyQuery",
    edge_filters: "AnyFilter | list[AnyFilter] | None" = None,
    filters: "AnyFilter | list[AnyFilter] | None" = None,
) -> ClosureQuery:
    """Create a ClosureQuery for BFS network expansion.

    Examples:
        closureQuery(typeTag("hub"), query(typeTag("junction")), [maxDistance(10)])
    """
    return ClosureQuery(
        source=source,
        candidates=candidates,
        edge_filters=edge_filters if isinstance(edge_filters, list) else [edge_filters] if edge_filters else [],
        filters=filters if isinstance(filters, list) else [filters] if filters else [],
    )


def materializedQuery(tag: str, q: "AnyQuery") -> MaterializedQuery:
    """Create a MaterializedQuery that materializes query results as a tag."""
    return MaterializedQuery(tag=tag, query=q)
