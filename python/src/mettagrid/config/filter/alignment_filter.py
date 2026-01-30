"""Alignment filter configuration and helper functions."""

from __future__ import annotations

from enum import StrEnum, auto
from typing import Literal, Optional

from pydantic import Field

from mettagrid.config.filter.filter import Filter, HandlerTarget


class AlignmentCondition(StrEnum):
    """Conditions for alignment filter checks."""

    ALIGNED = auto()  # target has any collective
    UNALIGNED = auto()  # target has no collective
    SAME_COLLECTIVE = auto()  # target has same collective as actor
    DIFFERENT_COLLECTIVE = auto()  # target has different collective than actor (but is aligned)
    NOT_SAME_COLLECTIVE = auto()  # target is not aligned to actor (unaligned OR different_collective)


class AlignmentFilter(Filter):
    """Filter that checks the alignment status of a target.

    Can check if target is aligned/unaligned, or if it's aligned to
    the same/different collective as the actor, or if it belongs to
    a specific collective.

    When `collective` is specified, checks if the entity belongs to that
    specific collective. Otherwise, uses `alignment` condition-based checks.
    """

    filter_type: Literal["alignment"] = "alignment"
    alignment: AlignmentCondition = Field(
        default=AlignmentCondition.SAME_COLLECTIVE,
        description=(
            "Alignment condition to check: "
            "'aligned' = target has any collective, "
            "'unaligned' = target has no collective, "
            "'same_collective' = target has same collective as actor, "
            "'different_collective' = target has different collective than actor (but is aligned), "
            "'not_same_collective' = target is not aligned to actor (unaligned OR different_collective)"
        ),
    )
    collective: Optional[str] = Field(
        default=None,
        description="If set, check if entity belongs to this specific collective",
    )


# ===== Helper Filter Functions =====


def isAlignedToActor() -> AlignmentFilter:
    """Filter: target is aligned to actor (same collective)."""
    return AlignmentFilter(target=HandlerTarget.TARGET, alignment=AlignmentCondition.SAME_COLLECTIVE)


def isNotAlignedToActor() -> AlignmentFilter:
    """Filter: target is NOT aligned to actor (unaligned OR different collective)."""
    return AlignmentFilter(target=HandlerTarget.TARGET, alignment=AlignmentCondition.NOT_SAME_COLLECTIVE)


def isAlignedTo(collective: Optional[str]) -> AlignmentFilter:
    """Filter: target is aligned to the specified collective, or unaligned if None.

    Args:
        collective: Name of collective to check alignment to, or None for unaligned.
    """
    if collective is None:
        return AlignmentFilter(target=HandlerTarget.TARGET, alignment=AlignmentCondition.UNALIGNED)
    return AlignmentFilter(target=HandlerTarget.TARGET, collective=collective)


def isNeutral() -> AlignmentFilter:
    """Filter: target has no collective (is unaligned/neutral)."""
    return AlignmentFilter(target=HandlerTarget.TARGET, alignment=AlignmentCondition.UNALIGNED)


def isEnemy() -> AlignmentFilter:
    """Filter: target is aligned but to a different collective than actor (enemy)."""
    return AlignmentFilter(target=HandlerTarget.TARGET, alignment=AlignmentCondition.DIFFERENT_COLLECTIVE)
