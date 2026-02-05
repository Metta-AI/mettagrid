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
    isNotAlignedTo,
    isNotAlignedToActor,
    isNotNeutral,
)
from mettagrid.config.filter.filter import AnyFilter, Filter, HandlerTarget, NotFilter, OrFilter, anyOf, isNot
from mettagrid.config.filter.game_value_filter import GameValueFilter
from mettagrid.config.filter.near_filter import NearFilter, isNear
from mettagrid.config.filter.resource_filter import (
    ResourceFilter,
    actorCollectiveHas,
    actorHas,
    actorHasAnyOf,
    targetCollectiveHas,
    targetHas,
    targetHasAnyOf,
)
from mettagrid.config.filter.tag_filter import TagFilter, hasTag, isA
from mettagrid.config.filter.vibe_filter import VibeFilter, actorVibe, targetVibe
from mettagrid.config.tag import Tag, typeTag

# Rebuild models with forward references now that all filter classes are defined
_filter_namespace = {
    "VibeFilter": VibeFilter,
    "ResourceFilter": ResourceFilter,
    "AlignmentFilter": AlignmentFilter,
    "TagFilter": TagFilter,
    "NearFilter": NearFilter,
    "GameValueFilter": GameValueFilter,
    "NotFilter": NotFilter,
    "OrFilter": OrFilter,
}
NotFilter.model_rebuild(_types_namespace=_filter_namespace)
OrFilter.model_rebuild(_types_namespace=_filter_namespace)
NearFilter.model_rebuild(_types_namespace=_filter_namespace)
GameValueFilter.model_rebuild(_types_namespace=_filter_namespace)

__all__ = [
    # Enums
    "HandlerTarget",
    "AlignmentCondition",
    # Filter classes
    "Filter",
    "NotFilter",
    "OrFilter",
    "VibeFilter",
    "ResourceFilter",
    "AlignmentFilter",
    "TagFilter",
    "NearFilter",
    "GameValueFilter",
    "AnyFilter",
    # Filter helpers
    "isNot",
    "anyOf",
    "isAlignedToActor",
    "isNotAlignedToActor",
    "isAlignedTo",
    "isNotAlignedTo",
    "isNeutral",
    "isNotNeutral",
    "isEnemy",
    "hasTag",
    "isA",
    "typeTag",
    "isNear",
    "actorHas",
    "targetHas",
    "actorCollectiveHas",
    "targetCollectiveHas",
    "actorHasAnyOf",
    "targetHasAnyOf",
    "actorVibe",
    "targetVibe",
    # Tag utilities
    "Tag",
]
