"""Mutation configuration classes and helper functions.

Mutations are the effects that handlers apply when triggered.
"""

from __future__ import annotations

from enum import StrEnum, auto
from typing import Annotated, Literal, Union

from pydantic import Discriminator, Field, Tag

from mettagrid.base_config import Config


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


class AlignTo(StrEnum):
    """Alignment target options for AlignmentMutation."""

    ACTOR_COLLECTIVE = auto()  # align to actor's collective
    NONE = auto()  # remove alignment


class Mutation(Config):
    """Base class for handler mutations."""

    pass


class ResourceDeltaMutation(Mutation):
    """Apply resource deltas to a target entity."""

    mutation_type: Literal["resource_delta"] = "resource_delta"
    target: EntityTarget = Field(description="Entity to apply deltas to")
    deltas: dict[str, int] = Field(
        default_factory=dict,
        description="Resource changes (positive = gain, negative = lose)",
    )


class ResourceTransferMutation(Mutation):
    """Transfer resources from one entity to another."""

    mutation_type: Literal["resource_transfer"] = "resource_transfer"
    from_target: EntityTarget = Field(description="Entity to take resources from")
    to_target: EntityTarget = Field(description="Entity to give resources to")
    resources: dict[str, int] = Field(
        default_factory=dict,
        description="Resources to transfer (amount, -1 = all available)",
    )


class AlignmentMutation(Mutation):
    """Update the collective alignment of a target."""

    mutation_type: Literal["alignment"] = "alignment"
    target: Literal["target"] = Field(
        default="target",
        description="Entity to align (only 'target' supported)",
    )
    align_to: AlignTo = Field(
        description="What to align the target to",
    )


class FreezeMutation(Mutation):
    """Freeze an entity for a duration."""

    mutation_type: Literal["freeze"] = "freeze"
    target: AlignmentEntityTarget = Field(description="Entity to freeze (actor or target)")
    duration: int = Field(description="Freeze duration in ticks")


class ClearInventoryMutation(Mutation):
    """Clear all resources in a limit group from inventory (set to 0)."""

    mutation_type: Literal["clear_inventory"] = "clear_inventory"
    target: EntityTarget = Field(description="Entity to clear inventory from")
    limit_name: str = Field(description="Name of the resource limit group to clear (e.g., 'gear')")


class AttackMutation(Mutation):
    """Combat mutation with weapon/armor/defense mechanics.

    Defense calculation:
    - weapon_power = sum(attacker_inventory[item] * weapon_weight)
    - armor_power = sum(target_inventory[item] * armor_weight) + vibe_bonus if vibing
    - damage_bonus = max(weapon_power - armor_power, 0)
    - cost_to_defend = defense_resources + damage_bonus

    If target can defend, defense resources are consumed and attack is blocked.
    Otherwise, on_success mutations are applied.
    """

    mutation_type: Literal["attack"] = "attack"
    defense_resources: dict[str, int] = Field(
        default_factory=dict,
        description="Resources target needs to block the attack",
    )
    armor_resources: dict[str, int] = Field(
        default_factory=dict,
        description="Target resources that reduce damage (resource -> weight)",
    )
    weapon_resources: dict[str, int] = Field(
        default_factory=dict,
        description="Attacker resources that increase damage (resource -> weight)",
    )
    vibe_bonus: dict[str, int] = Field(
        default_factory=dict,
        description="Per-vibe armor bonus when vibing a matching resource",
    )
    on_success: list["AnyMutation"] = Field(
        default_factory=list,
        description="Mutations to apply when attack succeeds",
    )


AnyMutation = Annotated[
    Union[
        Annotated[ResourceDeltaMutation, Tag("resource_delta")],
        Annotated[ResourceTransferMutation, Tag("resource_transfer")],
        Annotated[AlignmentMutation, Tag("alignment")],
        Annotated[FreezeMutation, Tag("freeze")],
        Annotated[ClearInventoryMutation, Tag("clear_inventory")],
        Annotated[AttackMutation, Tag("attack")],
    ],
    Discriminator("mutation_type"),
]

# Update forward references
AttackMutation.model_rebuild()


# ===== Helper Mutation Functions =====
# Factory functions for creating common mutation configurations


def Align() -> AlignmentMutation:
    """Mutation: align target to actor's collective."""
    return AlignmentMutation(target="target", align_to=AlignTo.ACTOR_COLLECTIVE)


def RemoveAlignment() -> AlignmentMutation:
    """Mutation: remove target's alignment (set collective to none)."""
    return AlignmentMutation(target="target", align_to=AlignTo.NONE)


def Withdraw(resources: dict[str, int]) -> ResourceTransferMutation:
    """Mutation: transfer resources from target to actor.

    Args:
        resources: Map of resource name to amount. Use -1 for "all available".
    """
    return ResourceTransferMutation(from_target=EntityTarget.TARGET, to_target=EntityTarget.ACTOR, resources=resources)


def Deposit(resources: dict[str, int]) -> ResourceTransferMutation:
    """Mutation: transfer resources from actor to target.

    Args:
        resources: Map of resource name to amount. Use -1 for "all available".
    """
    return ResourceTransferMutation(from_target=EntityTarget.ACTOR, to_target=EntityTarget.TARGET, resources=resources)


def CollectiveDeposit(resources: dict[str, int]) -> ResourceTransferMutation:
    """Mutation: transfer resources from actor to actor's collective.

    Args:
        resources: Map of resource name to amount. Use -1 for "all available".
    """
    return ResourceTransferMutation(
        from_target=EntityTarget.ACTOR, to_target=EntityTarget.ACTOR_COLLECTIVE, resources=resources
    )


def CollectiveWithdraw(resources: dict[str, int]) -> ResourceTransferMutation:
    """Mutation: transfer resources from actor's collective to actor.

    Args:
        resources: Map of resource name to amount. Use -1 for "all available".
    """
    return ResourceTransferMutation(
        from_target=EntityTarget.ACTOR_COLLECTIVE, to_target=EntityTarget.ACTOR, resources=resources
    )


def UpdateTarget(deltas: dict[str, int]) -> ResourceDeltaMutation:
    """Mutation: apply resource deltas to target.

    Args:
        deltas: Map of resource name to delta (positive = gain, negative = lose).
    """
    return ResourceDeltaMutation(target=EntityTarget.TARGET, deltas=deltas)


def UpdateActor(deltas: dict[str, int]) -> ResourceDeltaMutation:
    """Mutation: apply resource deltas to actor.

    Args:
        deltas: Map of resource name to delta (positive = gain, negative = lose).
    """
    return ResourceDeltaMutation(target=EntityTarget.ACTOR, deltas=deltas)


def TargetCollectiveUpdate(deltas: dict[str, int]) -> ResourceDeltaMutation:
    """Mutation: apply resource deltas to target's collective.

    Args:
        deltas: Map of resource name to delta (positive = gain, negative = lose).
    """
    return ResourceDeltaMutation(target=EntityTarget.TARGET_COLLECTIVE, deltas=deltas)


def ActorCollectiveUpdate(deltas: dict[str, int]) -> ResourceDeltaMutation:
    """Mutation: apply resource deltas to actor's collective.

    Args:
        deltas: Map of resource name to delta (positive = gain, negative = lose).
    """
    return ResourceDeltaMutation(target=EntityTarget.ACTOR_COLLECTIVE, deltas=deltas)
