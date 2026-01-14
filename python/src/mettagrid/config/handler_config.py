"""Handler configuration classes and helper functions.

This module provides a data-driven system for configuring handlers on GridObjects.
There are three types of handlers:
  - on_use: Triggered when agent uses/activates an object (context: actor=agent, target=object)
  - on_update: Triggered after mutations are applied (context: actor=null, target=object)
  - aoe: Triggered per-tick for objects within radius (context: actor=source, target=affected)

Handlers consist of filters (conditions that must be met) and mutations (effects that are applied).
"""

from __future__ import annotations

from pydantic import Field

from mettagrid.base_config import Config

# Import filters from filter_config
from mettagrid.config.filter_config import (
    ActorCollectiveHas,
    ActorHas,
    AlignmentCondition,
    AlignmentFilter,
    AlignmentTarget,
    AnyFilter,
    Filter,
    HandlerTarget,
    ResourceFilter,
    TargetCollectiveHas,
    TargetHas,
    VibeFilter,
    hasCollective,
    isAligned,
    isEnemy,
    isNeutral,
    isNotAligned,
)

# Import mutations from mutation_config
from mettagrid.config.mutation_config import (
    ActorCollectiveUpdate,
    Align,
    AlignmentEntityTarget,
    AlignmentMutation,
    AlignTo,
    AnyMutation,
    AttackMutation,
    ClearInventoryMutation,
    CollectiveDeposit,
    CollectiveWithdraw,
    Deposit,
    EntityTarget,
    FreezeMutation,
    Mutation,
    RemoveAlignment,
    ResourceDeltaMutation,
    ResourceTransferMutation,
    TargetCollectiveUpdate,
    UpdateActor,
    UpdateTarget,
    Withdraw,
)


class AOEEffectConfig(Config):
    """Simplified AOE effect configuration.

    This provides a simpler interface for common AOE patterns compared to full handlers.
    AOEs apply resource deltas to entities within range, optionally filtered by alignment.
    """

    range: int = Field(ge=0, description="Radius of the AOE effect")
    resource_deltas: dict[str, int] = Field(
        default_factory=dict,
        description="Resource changes to apply to affected entities",
    )
    filters: list[AnyFilter] = Field(
        default_factory=list,
        description="Filters to determine which entities are affected",
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
    "AlignmentTarget",
    "AlignmentCondition",
    "AlignTo",
    "EntityTarget",
    "AlignmentEntityTarget",
    # Filter classes
    "Filter",
    "VibeFilter",
    "ResourceFilter",
    "AlignmentFilter",
    "AnyFilter",
    # Mutation classes
    "Mutation",
    "ResourceDeltaMutation",
    "ResourceTransferMutation",
    "AlignmentMutation",
    "FreezeMutation",
    "ClearInventoryMutation",
    "AttackMutation",
    "AnyMutation",
    # Config classes
    "AOEEffectConfig",
    "Handler",
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
    # Mutation helpers
    "Align",
    "RemoveAlignment",
    "Withdraw",
    "Deposit",
    "CollectiveDeposit",
    "CollectiveWithdraw",
    "UpdateTarget",
    "UpdateActor",
    "TargetCollectiveUpdate",
    "ActorCollectiveUpdate",
]
