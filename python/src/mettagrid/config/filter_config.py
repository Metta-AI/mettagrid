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
    NearFilter,
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
    isNotAlignedToActor,
    targetCollectiveHas,
    targetHas,
)

__all__ = [
    # Enums
    "HandlerTarget",
    "AlignmentCondition",
    # Filter classes
    "Filter",
    "VibeFilter",
    "ResourceFilter",
    "AlignmentFilter",
    "TagFilter",
    "NearFilter",
    "AnyFilter",
    # Filter helpers
    "isAlignedToActor",
    "isNotAlignedToActor",
    "isAlignedTo",
    "isNeutral",
    "isEnemy",
    "hasTag",
    "isA",
    "isNear",
    "actorHas",
    "targetHas",
    "actorCollectiveHas",
    "targetCollectiveHas",
]
