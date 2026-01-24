"""Clear inventory mutation configuration."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from mettagrid.config.mutation.mutation import EntityTarget, Mutation


class ClearInventoryMutation(Mutation):
    """Clear all resources in a limit group from inventory (set to 0)."""

    mutation_type: Literal["clear_inventory"] = "clear_inventory"
    target: EntityTarget = Field(description="Entity to clear inventory from")
    limit_name: str = Field(description="Name of the resource limit group to clear (e.g., 'gear')")
