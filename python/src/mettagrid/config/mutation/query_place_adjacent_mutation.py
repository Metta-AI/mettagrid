"""Query-driven adjacent placement mutation configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import Field

from mettagrid.config.mutation.mutation import EntityTarget, Mutation

if TYPE_CHECKING:
    from mettagrid.config.query import AnyQuery


class QueryPlaceAdjacentMutation(Mutation):
    """Place an entity in an empty cardinal-adjacent cell around a queried object."""

    mutation_type: Literal["query_place_adjacent"] = "query_place_adjacent"
    query: "AnyQuery" = Field(description="Query to find anchor objects")
    target: EntityTarget = Field(default=EntityTarget.ACTOR, description="Entity to place")


def queryPlaceAdjacent(
    query: "AnyQuery",
    *,
    target: EntityTarget = EntityTarget.ACTOR,
) -> QueryPlaceAdjacentMutation:
    """Place an entity next to the first query result with a free cardinal neighbor."""

    return QueryPlaceAdjacentMutation(query=query, target=target)
