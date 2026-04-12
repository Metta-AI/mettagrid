"""Change vibe mutation configuration."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from mettagrid.config.mutation.mutation import EntityTarget, Mutation


class ChangeVibeMutation(Mutation):
    """Set the vibe on a target entity."""

    mutation_type: Literal["change_vibe"] = "change_vibe"
    target: EntityTarget = Field(default=EntityTarget.TARGET, description="Entity to change vibe on")
    vibe_name: str = Field(default="default", description="Vibe name to set")


def changeTargetVibe(vibe_name: str) -> ChangeVibeMutation:
    """Set the target's vibe."""
    return ChangeVibeMutation(target=EntityTarget.TARGET, vibe_name=vibe_name)
