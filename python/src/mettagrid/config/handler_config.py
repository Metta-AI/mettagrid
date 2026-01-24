"""Handler configuration classes and helper functions.

This module provides a data-driven system for configuring handlers on GridObjects.
There are three types of handlers:
  - on_use: Triggered when agent uses/activates an object (context: actor=agent, target=object)
  - on_update: Triggered after mutations are applied (context: actor=null, target=object)
  - aoe: Triggered per-tick for objects within radius (context: actor=source, target=affected)

Handlers consist of filters (conditions that must be met) and mutations (effects that are applied).
"""

from __future__ import annotations

from typing import Optional

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


class AOEEffectConfig(Config):
    """Configuration for Area of Effect (AOE) resource effects.

    When attached to a grid object, objects with inventory within range receive the resource_deltas each tick.

    Target filtering:
    - target_tags: If set, only objects with at least one matching tag are affected.
                   If None or empty, all HasInventory objects are affected.
                   Agents are always checked every tick (they move).
                   Static objects are registered/unregistered with the AOE for efficiency.
    - filters: List of filters that must all pass for the effect to apply.
               Uses the same filter types as activation handlers (AlignmentFilter, VibeFilter, ResourceFilter).
               In AOE context, "actor" refers to the AOE source object and "target" refers to the affected object.
    """

    range: int = Field(ge=0, description="Radius of effect (L-infinity/Chebyshev distance)")
    resource_deltas: dict[str, int] = Field(
        default_factory=dict,
        description="Resource changes per tick for objects in range. Positive = gain, negative = lose.",
    )
    target_tags: Optional[list[str]] = Field(
        default=None,
        description="If set, only objects with at least one matching tag are affected. "
        "If None, all HasInventory objects are affected.",
    )
    filters: list[AnyFilter] = Field(
        default_factory=list,
        description="Filters that must all pass for effect to apply. "
        "In AOE context, 'actor' = source object, 'target' = affected object.",
    )


class Handler(Config):
    """Configuration for a handler on GridObject.

    Used for all three handler types:
      - on_use: Triggered when agent uses/activates this object
      - on_update: Triggered after mutations are applied to this object
      - aoe: Triggered per-tick for objects within radius

    For on_use handlers, the first handler where all filters pass has its mutations applied.
    For on_update and aoe handlers, all handlers where filters pass have their mutations applied.

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
    "AOEEffectConfig",
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
