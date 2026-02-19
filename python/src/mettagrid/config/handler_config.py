"""Handler configuration classes and helper functions.

This module provides a data-driven system for configuring handlers on GridObjects.
There are two types of handlers:
  - on_use: Triggered when agent uses/activates an object (context: actor=agent, target=object)
  - aoe: Triggered per-tick for objects within radius (context: actor=source, target=affected)

Handlers consist of filters (conditions that must be met) and mutations (effects that are applied).
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import Field

from mettagrid.base_config import Config
from mettagrid.config.filter import (
    AlignmentCondition,
    AlignmentFilter,
    AnyFilter,
    AnyQuery,
    ClosureQuery,
    Filter,
    HandlerTarget,
    MaxDistanceFilter,
    NotFilter,
    Query,
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
    query,
    targetCollectiveHas,
    targetHas,
)
from mettagrid.config.mutation import (
    AddTagMutation,
    AlignmentMutation,
    AlignTo,
    AnyMutation,
    AttackMutation,
    ClearInventoryMutation,
    EntityTarget,
    FreezeMutation,
    Mutation,
    QueryInventoryMutation,
    RecomputeQueryTagMutation,
    RemoveTagMutation,
    RemoveTagsWithPrefixMutation,
    ResourceDeltaMutation,
    ResourceTransferMutation,
    StatsMutation,
    StatsTarget,
    addTag,
    alignTo,
    alignToActor,
    collectiveDeposit,
    collectiveWithdraw,
    deposit,
    logStat,
    queryDelta,
    queryDeposit,
    queryWithdraw,
    recomputeQueryTag,
    removeAlignment,
    removeTag,
    removeTagPrefix,
    updateActor,
    updateActorCollective,
    updateTarget,
    updateTargetCollective,
    withdraw,
)


class Handler(Config):
    """Configuration for a handler on GridObject.

    Used for both handler types:
      - on_use: Triggered when agent uses/activates this object
      - aoe: Triggered per-tick for objects within radius

    For on_use handlers, the first handler where all filters pass has its mutations applied.
    For aoe handlers, all handlers where filters pass have their mutations applied.

    The handler name is provided as the dict key when defining handlers on a GridObject.
    """

    filters: Sequence[AnyFilter] = Field(
        default_factory=list,
        description="All filters must pass for handler to trigger",
    )
    mutations: list[AnyMutation] = Field(
        default_factory=list,
        description="Mutations applied when handler triggers",
    )


class AOEConfig(Handler):
    """Configuration for Area of Effect (AOE) systems.

    Extends Handler with AOE-specific fields. Inherits filters and mutations.

    Supports two modes:
    - Static (is_static=True, default): Pre-computed cell registration for efficiency.
      Good for stationary objects like turrets, healing stations.
    - Mobile (is_static=False): Re-evaluated each tick for moving sources.
      Good for agents with auras.

    In AOE context, "actor" refers to the AOE source object and "target" refers to
    the affected object.

    Effects:
    - mutations: Applied every tick to targets that pass filters and are in range.
    - presence_deltas: One-time resource changes when target enters/exits AOE.
      On enter: apply +delta, on exit: apply -delta.
    """

    radius: int = Field(default=1, ge=0, description="Radius of effect (Euclidean distance)")
    is_static: bool = Field(
        default=True,
        description="If True (default), pre-compute affected cells at registration (for static sources). "
        "If False, re-evaluate position each tick (for moving sources like agents).",
    )
    effect_self: bool = Field(
        default=False,
        description="If True, the AOE source is affected by its own AOE.",
    )
    presence_deltas: dict[str, int] = Field(
        default_factory=dict,
        description="One-time resource changes when target enters/exits AOE. "
        "On enter: apply +delta, on exit: apply -delta. Keys are resource names.",
    )


# Re-export all handler-related types
__all__ = [
    # Enums
    "HandlerTarget",
    "AlignmentCondition",
    "AlignTo",
    "EntityTarget",
    "StatsTarget",
    # Filter classes
    "Filter",
    "VibeFilter",
    "ResourceFilter",
    "AlignmentFilter",
    "TagFilter",
    "MaxDistanceFilter",
    "NotFilter",
    "AnyFilter",
    # Mutation classes
    "Mutation",
    "ResourceDeltaMutation",
    "ResourceTransferMutation",
    "AlignmentMutation",
    "FreezeMutation",
    "ClearInventoryMutation",
    "AttackMutation",
    "StatsMutation",
    "AddTagMutation",
    "RemoveTagMutation",
    "RemoveTagsWithPrefixMutation",
    "RecomputeQueryTagMutation",
    "QueryInventoryMutation",
    "AnyMutation",
    # Config classes
    "AOEConfig",
    "Handler",
    # Query
    "Query",
    "ClosureQuery",
    "AnyQuery",
    "query",
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
    # Mutation helpers
    "alignToActor",
    "alignTo",
    "removeAlignment",
    "logStat",
    "addTag",
    "removeTag",
    "removeTagPrefix",
    "recomputeQueryTag",
    "queryDeposit",
    "queryWithdraw",
    "queryDelta",
    "withdraw",
    "deposit",
    "collectiveDeposit",
    "collectiveWithdraw",
    "updateTarget",
    "updateActor",
    "updateTargetCollective",
    "updateActorCollective",
]
