"""Mutation configuration classes and helper functions.

Mutations are the effects that handlers apply when triggered.
"""

# AnyMutation defined here where all concrete types are real imports (no strings).
from typing import Annotated, Union  # noqa: E402

from pydantic import (
    Discriminator,  # noqa: E402
    Tag,  # noqa: E402
)

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
from mettagrid.config.mutation.mutation import AlignmentEntityTarget, EntityTarget, Mutation
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
from mettagrid.config.mutation.tag_mutation import AddTagMutation, RemoveTagMutation, addTag, removeTag

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
        Annotated[SetGameValueMutation, Tag("set_game_value")],
    ],
    Discriminator("mutation_type"),
]

# Rebuild models that reference "AnyMutation" as a string annotation.
AttackMutation.model_rebuild(_types_namespace={"AnyMutation": AnyMutation})

__all__ = [
    # Enums
    "EntityTarget",
    "AlignmentEntityTarget",
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
    "SetGameValueMutation",
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
    "withdraw",
    "deposit",
    "collectiveDeposit",
    "collectiveWithdraw",
    "updateTarget",
    "updateActor",
    "updateTargetCollective",
    "updateActorCollective",
]
