"""Handler configuration classes and helper functions.

This module provides a data-driven system for configuring handlers on GridObjects.
There are two types of handlers:
  - on_use: Triggered when agent uses/activates an object (context: actor=agent, target=object)
  - aoe: Triggered per-tick for objects within radius (context: actor=source, target=affected)

Handlers consist of filters (conditions that must be met) and mutations (effects that are applied).
"""

from __future__ import annotations

from pydantic import Field

from mettagrid.base_config import Config
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
from mettagrid.config.mutation import (
    AddTagMutation,
    AlignmentEntityTarget,
    AlignmentMutation,
    AlignTo,
    AnyMutation,
    AttackMutation,
    ClearInventoryMutation,
    EntityTarget,
    FreezeMutation,
    Mutation,
    RemoveTagMutation,
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
    removeAlignment,
    removeTag,
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

    filters: list[AnyFilter] = Field(
        default_factory=list,
        description="All filters must pass for handler to trigger",
    )
    mutations: list[AnyMutation] = Field(
        default_factory=list,
        description="Mutations applied when handler triggers",
    )
    radius: int = Field(
        default=0,
        ge=0,
        description="AOE radius (L-infinity/Chebyshev distance). Only used for aoe handlers.",
    )


class AOEConfig(Handler):
    """Configuration for Area of Effect (AOE) systems.

    Extends Handler with AOE-specific fields. Inherits filters, mutations, and radius.

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

    radius: int = Field(default=1, ge=0, description="Radius of effect (L-infinity/Chebyshev distance)")
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
    "AlignmentEntityTarget",
    "StatsTarget",
    # Filter classes
    "Filter",
    "VibeFilter",
    "ResourceFilter",
    "AlignmentFilter",
    "TagFilter",
    "NearFilter",
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
    "AnyMutation",
    # Config classes
    "AOEConfig",
    "Handler",
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
    # Mutation helpers
    "alignToActor",
    "alignTo",
    "removeAlignment",
    "logStat",
    "addTag",
    "removeTag",
    "withdraw",
    "deposit",
    "collectiveDeposit",
    "collectiveWithdraw",
    "updateTarget",
    "updateActor",
    "updateTargetCollective",
    "updateActorCollective",
]
