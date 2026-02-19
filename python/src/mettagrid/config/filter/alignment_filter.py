"""Alignment filter configuration and helper functions."""

from __future__ import annotations

from enum import auto
from typing import TYPE_CHECKING, Literal, Optional

from pydantic import Field

from mettagrid.base_config import ConfigStrEnum
from mettagrid.config.filter.filter import Filter, HandlerTarget, isNot

if TYPE_CHECKING:
    from mettagrid.config.filter.filter import NotFilter


class AlignmentCondition(ConfigStrEnum):
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


def isNotAlignedToActor() -> "NotFilter":
    """Filter: target is NOT aligned to actor (unaligned OR different collective).

    Uses isNot() wrapper around same_collective check.
    """
    return isNot(AlignmentFilter(target=HandlerTarget.TARGET, alignment=AlignmentCondition.SAME_COLLECTIVE))


def isAlignedTo(collective: Optional[str]) -> AlignmentFilter:
    """Filter: target is aligned to the specified collective, or unaligned if None.

    Args:
        collective: Name of collective to check alignment to, or None for unaligned.
    """
    if collective is None:
        return AlignmentFilter(target=HandlerTarget.TARGET, alignment=AlignmentCondition.UNALIGNED)
    return AlignmentFilter(target=HandlerTarget.TARGET, collective=collective)


def isNotAlignedTo(collective: str) -> "NotFilter":
    """Filter: target is NOT aligned to the specified collective.

    This is the negated form of isAlignedTo(). Useful for checking if an entity
    does NOT belong to a specific collective (e.g., not part of "cogs").

    Args:
        collective: Name of collective to check non-alignment to.
    """
    return isNot(AlignmentFilter(target=HandlerTarget.TARGET, collective=collective))


def isNeutral() -> AlignmentFilter:
    """Filter: target has no collective (is unaligned/neutral)."""
    return AlignmentFilter(target=HandlerTarget.TARGET, alignment=AlignmentCondition.UNALIGNED)


def isNotNeutral() -> AlignmentFilter:
    """Filter: target has a collective (is aligned/not neutral)."""
    return AlignmentFilter(target=HandlerTarget.TARGET, alignment=AlignmentCondition.ALIGNED)


def isEnemy() -> AlignmentFilter:
    """Filter: target is aligned but to a different collective than actor (enemy)."""
    return AlignmentFilter(target=HandlerTarget.TARGET, alignment=AlignmentCondition.DIFFERENT_COLLECTIVE)
