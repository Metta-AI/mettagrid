"""Filter configuration classes and helper functions.

This module defines filter types used to determine when handlers should trigger.
Filters check conditions on actors, targets, or their collectives.
"""

# AnyFilter defined here where all concrete types are real imports (no strings).
from typing import Annotated, Union  # noqa: E402

from pydantic import Discriminator  # noqa: E402
from pydantic import Tag as PydanticTag  # noqa: E402

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
from mettagrid.config.filter.filter import Filter, HandlerTarget, NotFilter, OrFilter, anyOf, isNot
from mettagrid.config.filter.game_value_filter import GameValueFilter
from mettagrid.config.filter.max_distance_filter import MaxDistanceFilter, isNear
from mettagrid.config.filter.resource_filter import (
    ResourceFilter,
    actorCollectiveHas,
    actorHas,
    actorHasAnyOf,
    targetCollectiveHas,
    targetHas,
    targetHasAnyOf,
)
from mettagrid.config.filter.shared_tag_prefix_filter import (
    SharedTagPrefixFilter,
    sharedTagPrefix,
)
from mettagrid.config.filter.tag_filter import TagFilter, hasTag, isA
from mettagrid.config.filter.tag_prefix_filter import TagPrefixFilter, hasTagPrefix
from mettagrid.config.filter.vibe_filter import VibeFilter, actorVibe, targetVibe
from mettagrid.config.query import AnyQuery, ClosureQuery, MaterializedQuery, Query, materializedQuery, query
from mettagrid.config.tag import Tag, typeTag

AnyFilter = Annotated[
    Union[
        Annotated[VibeFilter, PydanticTag("vibe")],
        Annotated[ResourceFilter, PydanticTag("resource")],
        Annotated[AlignmentFilter, PydanticTag("alignment")],
        Annotated[TagFilter, PydanticTag("tag")],
        Annotated[SharedTagPrefixFilter, PydanticTag("shared_tag_prefix")],
        Annotated[TagPrefixFilter, PydanticTag("tag_prefix")],
        Annotated[MaxDistanceFilter, PydanticTag("max_distance")],
        Annotated[GameValueFilter, PydanticTag("game_value")],
        Annotated[NotFilter, PydanticTag("not")],
        Annotated[OrFilter, PydanticTag("or")],
    ],
    Discriminator("filter_type"),
]

# Rebuild models that reference "AnyFilter" or "AnyQuery" as string annotations.
_rebuild_ns = {
    "AnyFilter": AnyFilter,
    "AnyQuery": AnyQuery,
    "Query": Query,
    "MaterializedQuery": MaterializedQuery,
    "ClosureQuery": ClosureQuery,
}
NotFilter.model_rebuild(_types_namespace=_rebuild_ns)
OrFilter.model_rebuild(_types_namespace=_rebuild_ns)
Query.model_rebuild(_types_namespace=_rebuild_ns)
MaterializedQuery.model_rebuild(_types_namespace=_rebuild_ns)
ClosureQuery.model_rebuild(_types_namespace=_rebuild_ns)
MaxDistanceFilter.model_rebuild(_types_namespace=_rebuild_ns)

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
    "TagPrefixFilter",
    "SharedTagPrefixFilter",
    "MaxDistanceFilter",
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
    "hasTagPrefix",
    "sharedTagPrefix",
    # Tag utilities
    "Tag",
    # Query
    "Query",
    "MaterializedQuery",
    "ClosureQuery",
    "AnyQuery",
    "query",
    "materializedQuery",
]
