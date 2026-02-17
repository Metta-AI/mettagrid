"""Filter configuration classes and helper functions.

This module re-exports from mettagrid.config.filter for backwards compatibility.
"""

# Re-export everything from the filter subpackage
from mettagrid.config.filter import (
    AlignmentCondition,
    AlignmentFilter,
    AnyFilter,
    Filter,
    HandlerTarget,
    MaxDistanceFilter,
    NotFilter,
    ResourceFilter,
    TagFilter,
    VibeFilter,
    actorCollectiveHas,
    actorHas,
    hasTag,
    isA,
    isAlignedTo,
    isAlignedToActor,
    isEnemy,
    isNear,
    isNeutral,
    isNot,
    isNotAlignedTo,
    isNotAlignedToActor,
    isNotNeutral,
    targetCollectiveHas,
    targetHas,
)

__all__ = [
    # Enums
    "HandlerTarget",
    "AlignmentCondition",
    # Filter classes
    "Filter",
    "NotFilter",
    "VibeFilter",
    "ResourceFilter",
    "AlignmentFilter",
    "TagFilter",
    "MaxDistanceFilter",
    "AnyFilter",
    # Filter helpers
    "isNot",
    "isAlignedToActor",
    "isNotAlignedToActor",
    "isAlignedTo",
    "isNotAlignedTo",
    "isNeutral",
    "isNotNeutral",
    "isEnemy",
    "hasTag",
    "isA",
    "isNear",
    "actorHas",
    "targetHas",
    "actorCollectiveHas",
    "targetCollectiveHas",
]
