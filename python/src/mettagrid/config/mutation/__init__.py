"""Mutation configuration classes and helper functions.

Mutations are the effects that handlers apply when triggered.
"""

# AnyMutation defined here where all concrete types are real imports (no strings).
from typing import Annotated, Union  # noqa: E402

from pydantic import (
    Discriminator,  # noqa: E402
    Tag,  # noqa: E402
)

from mettagrid.config.filter import AnyFilter
from mettagrid.config.mutation.alignment_mutation import (
    AlignmentMutation,
    AlignTo,
    alignTo,
    alignToActor,
    removeAlignment,
)
from mettagrid.config.mutation.attack_mutation import AttackMutation
from mettagrid.config.mutation.clear_inventory_mutation import ClearInventoryMutation
from mettagrid.config.mutation.freeze_mutation import FreezeMutation
from mettagrid.config.mutation.game_value_mutation import SetGameValueMutation
from mettagrid.config.mutation.mutation import EntityTarget, Mutation
from mettagrid.config.mutation.query_inventory_mutation import (
    QueryInventoryMutation,
    queryDelta,
    queryDeposit,
    queryWithdraw,
)
from mettagrid.config.mutation.recompute_query_tag_mutation import RecomputeQueryTagMutation, recomputeQueryTag
from mettagrid.config.mutation.resource_mutation import (
    ResourceDeltaMutation,
    ResourceTransferMutation,
    collectiveDeposit,
    collectiveWithdraw,
    deposit,
    updateActor,
    updateActorCollective,
    updateTarget,
    updateTargetCollective,
    withdraw,
)
from mettagrid.config.mutation.stats_mutation import (
    StatsEntity,
    StatsMutation,
    StatsTarget,
    logActorAgentStat,
    logActorCollectiveStat,
    logStat,
    logStatToGame,
    logTargetAgentStat,
    logTargetCollectiveStat,
)
from mettagrid.config.mutation.tag_mutation import (
    AddTagMutation,
    RemoveTagMutation,
    RemoveTagsWithPrefix,
    RemoveTagsWithPrefixMutation,
    addTag,
    removeTag,
    removeTagPrefix,
)
from mettagrid.config.query import Query
from mettagrid.config.tag import Tag as TagType

AnyMutation = Annotated[
    Union[
        Annotated[ResourceDeltaMutation, Tag("resource_delta")],
        Annotated[ResourceTransferMutation, Tag("resource_transfer")],
        Annotated[AlignmentMutation, Tag("alignment")],
        Annotated[FreezeMutation, Tag("freeze")],
        Annotated[ClearInventoryMutation, Tag("clear_inventory")],
        Annotated[AttackMutation, Tag("attack")],
        Annotated[StatsMutation, Tag("stats")],
        Annotated[AddTagMutation, Tag("add_tag")],
        Annotated[RemoveTagMutation, Tag("remove_tag")],
        Annotated[RemoveTagsWithPrefixMutation, Tag("remove_tags_with_prefix")],
        Annotated[SetGameValueMutation, Tag("set_game_value")],
        Annotated[RecomputeQueryTagMutation, Tag("recompute_query_tag")],
        Annotated[QueryInventoryMutation, Tag("query_inventory")],
    ],
    Discriminator("mutation_type"),
]

_mutation_namespace = {
    "AnyQuery": Query,
    "AnyFilter": AnyFilter,
    "AnyMutation": AnyMutation,
    "Query": Query,
    "Tag": TagType,
    "ResourceDeltaMutation": ResourceDeltaMutation,
    "ResourceTransferMutation": ResourceTransferMutation,
    "FreezeMutation": FreezeMutation,
    "ClearInventoryMutation": ClearInventoryMutation,
    "AlignmentMutation": AlignmentMutation,
    "AttackMutation": AttackMutation,
    "StatsMutation": StatsMutation,
    "AddTagMutation": AddTagMutation,
    "RemoveTagMutation": RemoveTagMutation,
    "RemoveTagsWithPrefixMutation": RemoveTagsWithPrefixMutation,
    "SetGameValueMutation": SetGameValueMutation,
    "RecomputeQueryTagMutation": RecomputeQueryTagMutation,
    "QueryInventoryMutation": QueryInventoryMutation,
}
AttackMutation.model_rebuild(_types_namespace=_mutation_namespace)
SetGameValueMutation.model_rebuild(_types_namespace=_mutation_namespace)
RecomputeQueryTagMutation.model_rebuild(_types_namespace=_mutation_namespace)
QueryInventoryMutation.model_rebuild(_types_namespace=_mutation_namespace)

__all__ = [
    # Enums
    "EntityTarget",
    "AlignTo",
    "StatsTarget",
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
    "SetGameValueMutation",
    "RecomputeQueryTagMutation",
    "QueryInventoryMutation",
    "AnyMutation",
    # Mutation helpers
    "alignToActor",
    "alignTo",
    "removeAlignment",
    "logStat",
    "logStatToGame",
    "logTargetAgentStat",
    "logActorAgentStat",
    "logTargetCollectiveStat",
    "logActorCollectiveStat",
    "StatsEntity",
    "addTag",
    "removeTag",
    "removeTagPrefix",
    "RemoveTagsWithPrefix",
    "withdraw",
    "deposit",
    "collectiveDeposit",
    "collectiveWithdraw",
    "updateTarget",
    "updateActor",
    "updateTargetCollective",
    "updateActorCollective",
    "queryDeposit",
    "queryWithdraw",
    "queryDelta",
    "recomputeQueryTag",
]
