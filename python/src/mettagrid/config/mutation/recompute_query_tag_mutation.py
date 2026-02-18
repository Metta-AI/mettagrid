"""Recompute query tag mutation - triggers recomputation of a QueryTag."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from mettagrid.config.mutation.mutation import Mutation


class RecomputeQueryTagMutation(Mutation):
    """Trigger recomputation of a QueryTag's membership.

    When applied, the QuerySystem re-evaluates queries for all query tags
    whose names start with tag_prefix and updates their memberships.
    """

    mutation_type: Literal["recompute_query_tag"] = "recompute_query_tag"
    tag_prefix: str = Field(description="Prefix of query tags to recompute")


def recomputeQueryTag(tag_prefix: str) -> RecomputeQueryTagMutation:
    """Helper to create a RecomputeQueryTagMutation."""
    return RecomputeQueryTagMutation(tag_prefix=tag_prefix)
