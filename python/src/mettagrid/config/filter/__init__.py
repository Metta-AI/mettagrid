"""Filter configuration classes and helper functions.

This module defines filter types used to determine when handlers should trigger.
Filters check conditions on actors, targets, or their collectives.
"""

from mettagrid.config.filter.alignment_filter import (
    AlignmentCondition,
    AlignmentFilter,
    isAlignedTo,
    isAlignedToActor,
    isEnemy,
    isNeutral,
    isNotAlignedToActor,
)
from mettagrid.config.filter.filter import AnyFilter, Filter, HandlerTarget
from mettagrid.config.filter.near_filter import NearFilter, isNear
from mettagrid.config.filter.resource_filter import (
    ResourceFilter,
    actorCollectiveHas,
    actorHas,
    targetCollectiveHas,
    targetHas,
)
from mettagrid.config.filter.tag_filter import TagFilter, hasTag, isA, typeTag
from mettagrid.config.filter.vibe_filter import VibeFilter, actorVibe, targetVibe

# Rebuild models with forward references now that all filter classes are defined
NearFilter.model_rebuild()

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
    "actorVibe",
    "targetVibe",
    # Tag utilities
    "typeTag",
]
