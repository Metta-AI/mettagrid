"""Query inventory mutation configuration and helper functions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import Field

from mettagrid.config.mutation.mutation import EntityTarget, Mutation

if TYPE_CHECKING:
    from mettagrid.config.query import AnyQuery


class QueryInventoryMutation(Mutation):
    """Find objects via query and apply inventory deltas.

    Optionally transfers atomically from a source entity (transfer mode).
    When source is set, inverse deltas are applied to the source entity.
    """

    mutation_type: Literal["query_inventory"] = "query_inventory"
    query: "AnyQuery" = Field(description="Query to find objects to update")
    deltas: dict[str, int] = Field(
        default_factory=dict,
        description="Resource deltas to apply to query results",
    )
    source: EntityTarget | None = Field(
        default=None,
        description="If set, apply inverse deltas to this entity (transfer mode)",
    )


def queryDeposit(query: "AnyQuery", resources: dict[str, int]) -> QueryInventoryMutation:
    """Mutation: transfer resources from actor to query results.

    Args:
        query: Query to find destination objects
        resources: Map of resource name to amount to transfer
    """
    return QueryInventoryMutation(query=query, deltas=resources, source=EntityTarget.ACTOR)


def queryWithdraw(query: "AnyQuery", resources: dict[str, int]) -> QueryInventoryMutation:
    """Mutation: transfer resources from query results to actor.

    Args:
        query: Query to find source objects
        resources: Map of resource name to amount to transfer
    """
    return QueryInventoryMutation(
        query=query,
        deltas={k: -v for k, v in resources.items()},
        source=EntityTarget.ACTOR,
    )


def queryDelta(query: "AnyQuery", deltas: dict[str, int]) -> QueryInventoryMutation:
    """Mutation: apply resource deltas to query results (no source transfer).

    Args:
        query: Query to find objects to update
        deltas: Map of resource name to delta (positive = gain, negative = lose)
    """
    return QueryInventoryMutation(query=query, deltas=deltas)
