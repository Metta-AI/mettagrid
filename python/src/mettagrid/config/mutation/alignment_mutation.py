"""Alignment mutation configuration and helper functions."""

from __future__ import annotations

from enum import StrEnum, auto
from typing import Literal, Optional

from pydantic import Field

from mettagrid.config.mutation.mutation import Mutation


class AlignTo(StrEnum):
    """Alignment target options for AlignmentMutation."""

    ACTOR_COLLECTIVE = auto()  # align to actor's collective
    NONE = auto()  # remove alignment


class AlignmentMutation(Mutation):
    """Update the collective alignment of a target.

    Extended to support:
    - Aligning to actor's collective (align_to = actor_collective)
    - Removing alignment (align_to = none)
    - Aligning to a specific collective by name (collective parameter)

    When `collective` is specified, the target is aligned to that specific
    collective, ignoring the `align_to` field.
    """

    mutation_type: Literal["alignment"] = "alignment"
    target: Literal["target"] = Field(
        default="target",
        description="Entity to align (only 'target' supported)",
    )
    align_to: AlignTo = Field(
        default=AlignTo.ACTOR_COLLECTIVE,
        description="What to align the target to (ignored if collective is set)",
    )
    collective: Optional[str] = Field(
        default=None,
        description="If set, align target to this specific collective",
    )


# ===== Helper Mutation Functions =====


def alignToActor() -> AlignmentMutation:
    """Mutation: align target to actor's collective."""
    return AlignmentMutation(target="target", align_to=AlignTo.ACTOR_COLLECTIVE)


def alignTo(collective: Optional[str]) -> AlignmentMutation:
    """Mutation: align target to a specific collective, or remove alignment.

    Args:
        collective: Name of the collective to align target to, or None to remove alignment.
    """
    if collective is None:
        return AlignmentMutation(target="target", align_to=AlignTo.NONE)
    return AlignmentMutation(target="target", collective=collective)


def removeAlignment() -> AlignmentMutation:
    """Mutation: remove target's collective alignment (make neutral)."""
    return AlignmentMutation(target="target", align_to=AlignTo.NONE)
