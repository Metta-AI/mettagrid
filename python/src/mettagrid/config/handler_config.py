"""Handler configuration classes and helper functions.

This module provides a data-driven system for configuring handlers on GridObjects.
There are two types of handlers:
  - on_use: Triggered when agent uses/activates an object (context: actor=agent, target=object)
  - aoe: Triggered per-tick for objects within radius (context: actor=source, target=affected)

Handlers consist of filters (conditions that must be met) and mutations (effects that are applied).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Any, Literal, Union

from pydantic import Discriminator, Field
from pydantic import Tag as PydanticTag

from mettagrid.base_config import Config
from mettagrid.config.filter import (
    AnyFilter,
    AnyQuery,
    ClosureQuery,
    Filter,
    HandlerTarget,
    MaterializedQuery,
    MaxDistanceFilter,
    NotFilter,
    PeriodicFilter,
    Query,
    ResourceFilter,
    TagFilter,
    TagPrefixFilter,
    TargetIsUsableFilter,
    TargetLocEmptyFilter,
    VibeFilter,
    actorHas,
    actorHasTag,
    hasTag,
    hasTagPrefix,
    isA,
    isNear,
    isNot,
    materializedQuery,
    query,
    targetHas,
)
from mettagrid.config.mutation import (
    AddTagMutation,
    AnyMutation,
    AttackMutation,
    ClearInventoryMutation,
    EntityTarget,
    Mutation,
    QueryInventoryMutation,
    RecomputeMaterializedQueryMutation,
    RelocateMutation,
    RemoveTagMutation,
    RemoveTagsWithPrefixMutation,
    ResourceDeltaMutation,
    ResourceTransferMutation,
    SpawnObjectMutation,
    StatsMutation,
    StatsTarget,
    SwapMutation,
    UseTargetMutation,
    addTag,
    deposit,
    logStat,
    queryDelta,
    queryDeposit,
    queryWithdraw,
    recomputeMaterializedQuery,
    removeTag,
    removeTagPrefix,
    updateActor,
    updateTarget,
    withdraw,
)


class Handler(Config):
    """Configuration for a handler on GridObject.

    Used for both handler types:
      - on_use: Triggered when agent uses/activates this object
      - aoe: Triggered per-tick for objects within radius
      - move: Handlers in the move action handler chain

    The handler name is provided as the dict key when defining handlers on a GridObject,
    or via the name field when used in a list (e.g., MoveActionConfig.handlers).
    """

    name: str = Field(default="", description="Handler name (used when defined in a list rather than a dict)")
    filters: Sequence[AnyFilter] = Field(
        default_factory=list,
        description="All filters must pass for handler to trigger",
    )
    mutations: list[AnyMutation] = Field(
        default_factory=list,
        description="Mutations applied when handler triggers",
    )


class FirstMatch(Config):
    """Try handlers in order, stop on first success."""

    handler_type: Literal["first_match"] = "first_match"
    handlers: list[Handler | FirstMatch | AllOf] = Field(default_factory=list)


class AllOf(Config):
    """Apply all handlers where filters pass."""

    handler_type: Literal["all_of"] = "all_of"
    handlers: list[Handler | FirstMatch | AllOf] = Field(default_factory=list)


# Resolve forward references for recursive nesting
FirstMatch.model_rebuild()
AllOf.model_rebuild()


def _handler_discriminator(v: Any) -> str:
    if isinstance(v, dict):
        return v.get("handler_type", "handler")
    return getattr(v, "handler_type", "handler")


AnyHandler = Annotated[
    Union[
        Annotated[Handler, PydanticTag("handler")],
        Annotated[FirstMatch, PydanticTag("first_match")],
        Annotated[AllOf, PydanticTag("all_of")],
    ],
    Discriminator(_handler_discriminator),
]


def firstMatch(handlers: list) -> AnyHandler | None:
    """Create a FirstMatch composite handler, filtering out None entries and flattening nested FirstMatch."""
    flat: list[Handler | FirstMatch | AllOf] = []
    for h in handlers:
        if h is None:
            continue
        if isinstance(h, FirstMatch):
            flat.extend(h.handlers)
        else:
            flat.append(h)
    if len(flat) == 0:
        return None
    if len(flat) == 1:
        return flat[0]
    return FirstMatch(handlers=flat)


def allOf(handlers: list) -> AnyHandler | None:
    """Create an AllOf composite handler, filtering out None entries and flattening nested AllOf."""
    flat: list[Handler | FirstMatch | AllOf] = []
    for h in handlers:
        if h is None:
            continue
        if isinstance(h, AllOf):
            flat.extend(h.handlers)
        else:
            flat.append(h)
    if len(flat) == 0:
        return None
    if len(flat) == 1:
        return flat[0]
    return AllOf(handlers=flat)


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
    - Territory ownership is derived from fixed AOEs with no mutations and no
      presence_deltas. Influence is computed from radius with one-per-tile decay.
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
    "EntityTarget",
    "StatsTarget",
    # Filter classes
    "Filter",
    "VibeFilter",
    "ResourceFilter",
    "TagFilter",
    "TagPrefixFilter",
    "MaxDistanceFilter",
    "NotFilter",
    "TargetLocEmptyFilter",
    "TargetIsUsableFilter",
    "PeriodicFilter",
    "AnyFilter",
    # Mutation classes
    "Mutation",
    "ResourceDeltaMutation",
    "ResourceTransferMutation",
    "ClearInventoryMutation",
    "AttackMutation",
    "StatsMutation",
    "AddTagMutation",
    "RemoveTagMutation",
    "RemoveTagsWithPrefixMutation",
    "RecomputeMaterializedQueryMutation",
    "QueryInventoryMutation",
    "RelocateMutation",
    "SpawnObjectMutation",
    "SwapMutation",
    "UseTargetMutation",
    "AnyMutation",
    # Config classes
    "AOEConfig",
    "AllOf",
    "AnyHandler",
    "FirstMatch",
    "Handler",
    # Composite handler helpers
    "allOf",
    "firstMatch",
    # Query
    "Query",
    "MaterializedQuery",
    "ClosureQuery",
    "AnyQuery",
    "query",
    "materializedQuery",
    # Filter helpers
    "isNot",
    "hasTag",
    "actorHasTag",
    "hasTagPrefix",
    "isA",
    "isNear",
    "actorHas",
    "targetHas",
    # Mutation helpers
    "logStat",
    "addTag",
    "removeTag",
    "removeTagPrefix",
    "recomputeMaterializedQuery",
    "queryDeposit",
    "queryWithdraw",
    "queryDelta",
    "withdraw",
    "deposit",
    "updateTarget",
    "updateActor",
]
