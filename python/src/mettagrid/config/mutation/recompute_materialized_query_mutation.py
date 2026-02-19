"""Recompute materialized query mutation - triggers recomputation of a MaterializedQuery."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from mettagrid.config.mutation.mutation import Mutation


class RecomputeMaterializedQueryMutation(Mutation):
    """Trigger recomputation of a MaterializedQuery's membership.

    When applied, the QuerySystem re-evaluates queries for all materialized queries
    whose tag names start with tag_prefix and updates their memberships.
    """

    mutation_type: Literal["recompute_materialized_query"] = "recompute_materialized_query"
    tag_prefix: str = Field(description="Prefix of materialized query tags to recompute")


def recomputeMaterializedQuery(tag_prefix: str) -> RecomputeMaterializedQueryMutation:
    """Helper to create a RecomputeMaterializedQueryMutation."""
    return RecomputeMaterializedQueryMutation(tag_prefix=tag_prefix)
