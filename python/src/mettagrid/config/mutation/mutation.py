"""Base mutation configuration and common types."""

from __future__ import annotations

from enum import StrEnum, auto
from typing import TYPE_CHECKING, Annotated, Union

from pydantic import Discriminator, Tag

from mettagrid.base_config import Config

if TYPE_CHECKING:
    from mettagrid.config.mutation.alignment_mutation import AlignmentMutation
    from mettagrid.config.mutation.attack_mutation import AttackMutation
    from mettagrid.config.mutation.clear_inventory_mutation import ClearInventoryMutation
    from mettagrid.config.mutation.freeze_mutation import FreezeMutation
    from mettagrid.config.mutation.game_value_mutation import SetGameValueMutation
    from mettagrid.config.mutation.resource_mutation import ResourceDeltaMutation, ResourceTransferMutation
    from mettagrid.config.mutation.stats_mutation import StatsMutation
    from mettagrid.config.mutation.tag_mutation import AddTagMutation, RemoveTagMutation


class EntityTarget(StrEnum):
    """Target entity for mutation operations."""

    ACTOR = auto()
    TARGET = auto()
    ACTOR_COLLECTIVE = auto()
    TARGET_COLLECTIVE = auto()


class AlignmentEntityTarget(StrEnum):
    """Target entity for alignment/freeze operations (subset of EntityTarget)."""

    ACTOR = auto()
    TARGET = auto()


class Mutation(Config):
    """Base class for handler mutations."""

    pass


AnyMutation = Annotated[
    Union[
        Annotated["ResourceDeltaMutation", Tag("resource_delta")],
        Annotated["ResourceTransferMutation", Tag("resource_transfer")],
        Annotated["AlignmentMutation", Tag("alignment")],
        Annotated["FreezeMutation", Tag("freeze")],
        Annotated["ClearInventoryMutation", Tag("clear_inventory")],
        Annotated["AttackMutation", Tag("attack")],
        Annotated["StatsMutation", Tag("stats")],
        Annotated["AddTagMutation", Tag("add_tag")],
        Annotated["RemoveTagMutation", Tag("remove_tag")],
        Annotated["SetGameValueMutation", Tag("set_game_value")],
    ],
    Discriminator("mutation_type"),
]
