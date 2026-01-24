"""Mutation configuration classes and helper functions.

Mutations are the effects that handlers apply when triggered.
"""

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
from mettagrid.config.mutation.mutation import AlignmentEntityTarget, AnyMutation, EntityTarget, Mutation
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
from mettagrid.config.mutation.stats_mutation import StatsMutation, StatsTarget, logStat
from mettagrid.config.mutation.tag_mutation import AddTagMutation, RemoveTagMutation, addTag, removeTag

# Rebuild models with forward references now that AnyMutation is defined
AttackMutation.model_rebuild()

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
    "AnyMutation",
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
