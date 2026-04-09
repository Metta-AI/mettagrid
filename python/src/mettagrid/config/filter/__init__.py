"""Filter configuration classes and helper functions.

This module defines filter types used to determine when handlers should trigger.
Filters check conditions on actors or targets.
"""

# AnyFilter defined here where all concrete types are real imports (no strings).
from typing import Annotated, Union  # noqa: E402

from pydantic import Discriminator  # noqa: E402
from pydantic import Tag as PydanticTag  # noqa: E402

from mettagrid.config.filter.filter import Filter, HandlerTarget, NotFilter, OrFilter, anyOf, isNot
from mettagrid.config.filter.game_value_filter import GameValueFilter
from mettagrid.config.filter.max_distance_filter import MaxDistanceFilter, isNear, maxDistance
from mettagrid.config.filter.periodic_filter import PeriodicFilter
from mettagrid.config.filter.resource_filter import (
    ResourceFilter,
    actorHas,
    actorHasAnyOf,
    targetHas,
    targetHasAnyOf,
)
from mettagrid.config.filter.shared_tag_prefix_filter import (
    SharedTagPrefixFilter,
    sharedTagPrefix,
)
from mettagrid.config.filter.tag_filter import TagFilter, actorHasTag, hasTag, isA
from mettagrid.config.filter.tag_prefix_filter import TagPrefixFilter, actorHasTagPrefix, hasTagPrefix
from mettagrid.config.filter.target_is_usable_filter import TargetIsUsableFilter
from mettagrid.config.filter.target_loc_empty_filter import TargetLocEmptyFilter
from mettagrid.config.filter.vibe_filter import VibeFilter, actorVibe, targetVibe
from mettagrid.config.game_value import (
    AnyGameValue,
    ConstValue,
    InventoryValue,
    MaxGameValue,
    MinGameValue,
    QueryCountValue,
    QueryInventoryValue,
    RatioGameValue,
    StatValue,
    SumGameValue,
)
from mettagrid.config.query import (
    AnyQuery,
    ClosureQuery,
    MaterializedQuery,
    Query,
    closureQuery,
    materializedQuery,
    query,
)
from mettagrid.config.raycast_query import RaycastQuery, raycastQuery
from mettagrid.config.tag import typeTag

AnyFilter = Annotated[
    Union[
        Annotated[VibeFilter, PydanticTag("vibe")],
        Annotated[ResourceFilter, PydanticTag("resource")],
        Annotated[TagFilter, PydanticTag("tag")],
        Annotated[SharedTagPrefixFilter, PydanticTag("shared_tag_prefix")],
        Annotated[TagPrefixFilter, PydanticTag("tag_prefix")],
        Annotated[MaxDistanceFilter, PydanticTag("max_distance")],
        Annotated[GameValueFilter, PydanticTag("game_value")],
        Annotated[NotFilter, PydanticTag("not")],
        Annotated[OrFilter, PydanticTag("or")],
        Annotated[TargetLocEmptyFilter, PydanticTag("target_loc_empty")],
        Annotated[TargetIsUsableFilter, PydanticTag("target_is_usable")],
        Annotated[PeriodicFilter, PydanticTag("periodic")],
    ],
    Discriminator("filter_type"),
]


# Rebuild models that reference "AnyFilter" or "AnyQuery" as string annotations.
_rebuild_ns = {
    "AnyFilter": AnyFilter,
    "AnyQuery": AnyQuery,
    "AnyGameValue": AnyGameValue,
    "InventoryValue": InventoryValue,
    "StatValue": StatValue,
    "ConstValue": ConstValue,
    "SumGameValue": SumGameValue,
    "RatioGameValue": RatioGameValue,
    "MaxGameValue": MaxGameValue,
    "MinGameValue": MinGameValue,
    "Query": Query,
    "MaterializedQuery": MaterializedQuery,
    "ClosureQuery": ClosureQuery,
    "RaycastQuery": RaycastQuery,
}
for model in (
    NotFilter,
    OrFilter,
    Query,
    MaterializedQuery,
    ClosureQuery,
    MaxDistanceFilter,
    RaycastQuery,
    QueryInventoryValue,
    QueryCountValue,
):
    model.model_rebuild(_types_namespace=_rebuild_ns)

# RaycastSpawnMutation references AnyFilter — rebuild it now that AnyFilter is defined.
from mettagrid.config.mutation.raycast_spawn_mutation import RaycastSpawnMutation  # noqa: E402

RaycastSpawnMutation.model_rebuild(_types_namespace=_rebuild_ns)


__all__ = [
    # Enums
    "HandlerTarget",
    # Filter classes
    "Filter",
    "NotFilter",
    "OrFilter",
    "VibeFilter",
    "ResourceFilter",
    "TagFilter",
    "TagPrefixFilter",
    "SharedTagPrefixFilter",
    "MaxDistanceFilter",
    "GameValueFilter",
    "TargetLocEmptyFilter",
    "TargetIsUsableFilter",
    "PeriodicFilter",
    "AnyFilter",
    # Filter helpers
    "isNot",
    "anyOf",
    "hasTag",
    "actorHasTag",
    "isA",
    "typeTag",
    "isNear",
    "maxDistance",
    "raycastQuery",
    "actorHas",
    "targetHas",
    "actorHasAnyOf",
    "targetHasAnyOf",
    "actorVibe",
    "targetVibe",
    "hasTagPrefix",
    "actorHasTagPrefix",
    "sharedTagPrefix",
    # Query
    "Query",
    "MaterializedQuery",
    "ClosureQuery",
    "AnyQuery",
    "query",
    "closureQuery",
    "materializedQuery",
]
