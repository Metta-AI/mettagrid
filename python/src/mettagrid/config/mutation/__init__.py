"""Mutation configuration classes and helper functions.

Mutations are the effects that handlers apply when triggered.
"""

# AnyMutation defined here where all concrete types are real imports (no strings).
from typing import TYPE_CHECKING, Annotated, Any, Union  # noqa: E402

from pydantic import (
    Discriminator,  # noqa: E402
    Tag,  # noqa: E402
)

if TYPE_CHECKING:
    from mettagrid.config.filter import AnyFilter
else:
    AnyFilter = Any
from mettagrid.config.game_value import AnyGameValue
from mettagrid.config.mutation.attack_mutation import AttackMutation
from mettagrid.config.mutation.change_vibe_mutation import ChangeVibeMutation, changeTargetVibe
from mettagrid.config.mutation.clear_inventory_mutation import ClearInventoryMutation
from mettagrid.config.mutation.game_value_mutation import SetGameValueMutation
from mettagrid.config.mutation.mutation import EntityTarget, Mutation
from mettagrid.config.mutation.push_object_mutation import PushObjectMutation
from mettagrid.config.mutation.query_inventory_mutation import (
    QueryInventoryMutation,
    queryDelta,
    queryDeposit,
    queryWithdraw,
)
from mettagrid.config.mutation.raycast_spawn_mutation import RaycastSpawnMutation
from mettagrid.config.mutation.recompute_materialized_query_mutation import (
    RecomputeMaterializedQueryMutation,
    recomputeMaterializedQuery,
)
from mettagrid.config.mutation.relocate_mutation import RelocateMutation
from mettagrid.config.mutation.resource_mutation import (
    ResourceDeltaMutation,
    ResourceTransferMutation,
    deposit,
    updateActor,
    updateTarget,
    withdraw,
)
from mettagrid.config.mutation.spawn_object_mutation import SpawnObjectMutation
from mettagrid.config.mutation.stats_mutation import (
    StatsEntity,
    StatsMutation,
    StatsTarget,
    logActorAgentStat,
    logStat,
    logStatToGame,
    logTargetAgentStat,
)
from mettagrid.config.mutation.swap_mutation import SwapMutation
from mettagrid.config.mutation.tag_mutation import (
    AddTagMutation,
    RemoveTagMutation,
    RemoveTagsWithPrefix,
    RemoveTagsWithPrefixMutation,
    addTag,
    removeTag,
    removeTagPrefix,
)
from mettagrid.config.mutation.use_target_mutation import UseTargetMutation, useTarget
from mettagrid.config.query import AnyQuery, ClosureQuery, MaterializedQuery, Query

AnyMutation = Annotated[
    Union[
        Annotated[ResourceDeltaMutation, Tag("resource_delta")],
        Annotated[ResourceTransferMutation, Tag("resource_transfer")],
        Annotated[ClearInventoryMutation, Tag("clear_inventory")],
        Annotated[AttackMutation, Tag("attack")],
        Annotated[StatsMutation, Tag("stats")],
        Annotated[AddTagMutation, Tag("add_tag")],
        Annotated[RemoveTagMutation, Tag("remove_tag")],
        Annotated[RemoveTagsWithPrefixMutation, Tag("remove_tags_with_prefix")],
        Annotated[SetGameValueMutation, Tag("set_game_value")],
        Annotated[RecomputeMaterializedQueryMutation, Tag("recompute_materialized_query")],
        Annotated[QueryInventoryMutation, Tag("query_inventory")],
        Annotated[RelocateMutation, Tag("relocate")],
        Annotated[SpawnObjectMutation, Tag("spawn_object")],
        Annotated[SwapMutation, Tag("swap")],
        Annotated[UseTargetMutation, Tag("use_target")],
        Annotated[ChangeVibeMutation, Tag("change_vibe")],
        Annotated[RaycastSpawnMutation, Tag("raycast_spawn")],
        Annotated[PushObjectMutation, Tag("push_object")],
    ],
    Discriminator("mutation_type"),
]

_mutation_namespace = {
    "AnyQuery": AnyQuery,
    "AnyFilter": AnyFilter,
    "AnyGameValue": AnyGameValue,
    "AnyMutation": AnyMutation,
    "Query": Query,
    "MaterializedQuery": MaterializedQuery,
    "ClosureQuery": ClosureQuery,
    "ResourceDeltaMutation": ResourceDeltaMutation,
    "ResourceTransferMutation": ResourceTransferMutation,
    "ClearInventoryMutation": ClearInventoryMutation,
    "AttackMutation": AttackMutation,
    "StatsMutation": StatsMutation,
    "AddTagMutation": AddTagMutation,
    "RemoveTagMutation": RemoveTagMutation,
    "RemoveTagsWithPrefixMutation": RemoveTagsWithPrefixMutation,
    "SetGameValueMutation": SetGameValueMutation,
    "RecomputeMaterializedQueryMutation": RecomputeMaterializedQueryMutation,
    "QueryInventoryMutation": QueryInventoryMutation,
    "RelocateMutation": RelocateMutation,
    "SpawnObjectMutation": SpawnObjectMutation,
    "ChangeVibeMutation": ChangeVibeMutation,
    "RaycastSpawnMutation": RaycastSpawnMutation,
    "SwapMutation": SwapMutation,
    "UseTargetMutation": UseTargetMutation,
    "PushObjectMutation": PushObjectMutation,
}
AttackMutation.model_rebuild(_types_namespace=_mutation_namespace)
SetGameValueMutation.model_rebuild(_types_namespace=_mutation_namespace)
RecomputeMaterializedQueryMutation.model_rebuild(_types_namespace=_mutation_namespace)
QueryInventoryMutation.model_rebuild(_types_namespace=_mutation_namespace)
# RaycastSpawnMutation references AnyFilter — rebuild after filter module is loaded.
# Deferred: the filter __init__.py triggers this rebuild via the mutation namespace.

__all__ = [
    # Enums
    "EntityTarget",
    "StatsTarget",
    # Mutation classes
    "Mutation",
    "ResourceDeltaMutation",
    "ResourceTransferMutation",
    "ClearInventoryMutation",
    "AttackMutation",
    "ChangeVibeMutation",
    "StatsMutation",
    "AddTagMutation",
    "RemoveTagMutation",
    "RemoveTagsWithPrefixMutation",
    "SetGameValueMutation",
    "RecomputeMaterializedQueryMutation",
    "QueryInventoryMutation",
    "RelocateMutation",
    "SpawnObjectMutation",
    "RaycastSpawnMutation",
    "SwapMutation",
    "UseTargetMutation",
    "PushObjectMutation",
    "useTarget",
    "AnyMutation",
    # Mutation helpers
    "logStat",
    "logStatToGame",
    "logTargetAgentStat",
    "logActorAgentStat",
    "StatsEntity",
    "addTag",
    "removeTag",
    "removeTagPrefix",
    "RemoveTagsWithPrefix",
    "withdraw",
    "deposit",
    "updateTarget",
    "updateActor",
    "queryDeposit",
    "queryWithdraw",
    "queryDelta",
    "recomputeMaterializedQuery",
    "changeTargetVibe",
]
