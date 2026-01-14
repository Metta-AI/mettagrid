"""Filter configuration classes and helper functions.

This module defines filter types used to determine when handlers should trigger.
Filters check conditions on actors, targets, or their collectives.
"""

from __future__ import annotations

from enum import StrEnum, auto
from typing import Annotated, Literal, Union

from pydantic import Discriminator, Field, Tag

from mettagrid.base_config import Config
from mettagrid.config.mutation_config import AlignmentEntityTarget, EntityTarget

# Alias for backwards compatibility - HandlerTarget is the same as EntityTarget
HandlerTarget = EntityTarget

# Alias for backwards compatibility - AlignmentTarget is the same as AlignmentEntityTarget
AlignmentTarget = AlignmentEntityTarget


class AlignmentCondition(StrEnum):
    """Conditions for alignment filter checks."""

    ALIGNED = auto()  # target has any collective
    UNALIGNED = auto()  # target has no collective
    SAME_COLLECTIVE = auto()  # target has same collective as actor
    DIFFERENT_COLLECTIVE = auto()  # target has different collective than actor (but is aligned)
    NOT_SAME_COLLECTIVE = auto()  # target is not aligned to actor (unaligned OR different_collective)


class Filter(Config):
    """Base class for handler filters. All filters in a handler must pass."""

    target: HandlerTarget = Field(
        default=HandlerTarget.ACTOR,
        description="Entity to check the filter against",
    )


class VibeFilter(Filter):
    """Filter that checks if the target entity has a specific vibe."""

    filter_type: Literal["vibe"] = "vibe"
    vibe: str = Field(description="Vibe name that must match")


class ResourceFilter(Filter):
    """Filter that checks if the target entity has required resources."""

    filter_type: Literal["resource"] = "resource"
    resources: dict[str, int] = Field(
        default_factory=dict,
        description="Minimum resource amounts required",
    )


class AlignmentFilter(Filter):
    """Filter that checks the alignment status of a target.

    Can check if target is aligned/unaligned, or if it's aligned to
    the same/different collective as the actor.
    """

    filter_type: Literal["alignment"] = "alignment"
    target: AlignmentTarget = Field(
        default=AlignmentTarget.TARGET,
        description="Entity to check the filter against (only actor/target for alignment)",
    )
    alignment: AlignmentCondition = Field(
        description=(
            "Alignment condition to check: "
            "'aligned' = target has any collective, "
            "'unaligned' = target has no collective, "
            "'same_collective' = target has same collective as actor, "
            "'different_collective' = target has different collective than actor (but is aligned), "
            "'not_same_collective' = target is not aligned to actor (unaligned OR different_collective)"
        ),
    )


AnyFilter = Annotated[
    Union[
        Annotated[VibeFilter, Tag("vibe")],
        Annotated[ResourceFilter, Tag("resource")],
        Annotated[AlignmentFilter, Tag("alignment")],
    ],
    Discriminator("filter_type"),
]


# ===== Helper Filter Functions =====
# Factory functions for creating common filter configurations


def isAligned() -> AlignmentFilter:
    """Filter: target is aligned to actor (same collective)."""
    return AlignmentFilter(target=AlignmentTarget.TARGET, alignment=AlignmentCondition.SAME_COLLECTIVE)


def hasCollective() -> AlignmentFilter:
    """Filter: target has any collective alignment."""
    return AlignmentFilter(target=AlignmentTarget.TARGET, alignment=AlignmentCondition.ALIGNED)


def isNeutral() -> AlignmentFilter:
    """Filter: target has no alignment (unaligned)."""
    return AlignmentFilter(target=AlignmentTarget.TARGET, alignment=AlignmentCondition.UNALIGNED)


def isNotAligned() -> AlignmentFilter:
    """Filter: target is NOT aligned to actor (unaligned OR different collective)."""
    return AlignmentFilter(target=AlignmentTarget.TARGET, alignment=AlignmentCondition.NOT_SAME_COLLECTIVE)


def isEnemy() -> AlignmentFilter:
    """Filter: target is aligned to a different collective than actor."""
    return AlignmentFilter(target=AlignmentTarget.TARGET, alignment=AlignmentCondition.DIFFERENT_COLLECTIVE)


def ActorHas(resources: dict[str, int]) -> ResourceFilter:
    """Filter: actor has at least the specified resources."""
    return ResourceFilter(target=HandlerTarget.ACTOR, resources=resources)


def TargetHas(resources: dict[str, int]) -> ResourceFilter:
    """Filter: target has at least the specified resources."""
    return ResourceFilter(target=HandlerTarget.TARGET, resources=resources)


def ActorCollectiveHas(resources: dict[str, int]) -> ResourceFilter:
    """Filter: actor's collective has at least the specified resources."""
    return ResourceFilter(target=HandlerTarget.ACTOR_COLLECTIVE, resources=resources)


def TargetCollectiveHas(resources: dict[str, int]) -> ResourceFilter:
    """Filter: target's collective has at least the specified resources."""
    return ResourceFilter(target=HandlerTarget.TARGET_COLLECTIVE, resources=resources)


# Re-export all filter-related types
__all__ = [
    # Enums
    "HandlerTarget",
    "AlignmentTarget",
    "AlignmentCondition",
    # Filter classes
    "Filter",
    "VibeFilter",
    "ResourceFilter",
    "AlignmentFilter",
    "AnyFilter",
    # Filter helpers
    "isAligned",
    "hasCollective",
    "isNeutral",
    "isNotAligned",
    "isEnemy",
    "ActorHas",
    "TargetHas",
    "ActorCollectiveHas",
    "TargetCollectiveHas",
]
