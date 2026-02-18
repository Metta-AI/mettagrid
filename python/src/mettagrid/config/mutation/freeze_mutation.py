"""Freeze mutation configuration."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from mettagrid.config.mutation.mutation import EntityTarget, Mutation


class FreezeMutation(Mutation):
    """Freeze an entity for a duration."""

    mutation_type: Literal["freeze"] = "freeze"
    target: EntityTarget = Field(description="Entity to freeze (actor or target)")
    duration: int = Field(description="Freeze duration in ticks")
