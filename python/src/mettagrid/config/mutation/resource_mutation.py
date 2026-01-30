"""Resource mutation configurations and helper functions."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from mettagrid.config.mutation.mutation import EntityTarget, Mutation


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
    remove_source_when_empty: bool = Field(
        default=False,
        description="Remove source from grid when its inventory is fully depleted",
    )


# ===== Helper Mutation Functions =====


def withdraw(resources: dict[str, int], *, remove_when_empty: bool = False) -> ResourceTransferMutation:
    """Mutation: transfer resources from target to actor.

    Args:
        resources: Map of resource name to amount. Use -1 for "all available".
        remove_when_empty: If True, remove source from grid when its inventory is fully depleted.
    """
    return ResourceTransferMutation(
        from_target=EntityTarget.TARGET,
        to_target=EntityTarget.ACTOR,
        resources=resources,
        remove_source_when_empty=remove_when_empty,
    )


def deposit(resources: dict[str, int]) -> ResourceTransferMutation:
    """Mutation: transfer resources from actor to target.

    Args:
        resources: Map of resource name to amount. Use -1 for "all available".
    """
    return ResourceTransferMutation(from_target=EntityTarget.ACTOR, to_target=EntityTarget.TARGET, resources=resources)


def collectiveDeposit(resources: dict[str, int]) -> ResourceTransferMutation:
    """Mutation: transfer resources from actor to actor's collective.

    Args:
        resources: Map of resource name to amount. Use -1 for "all available".
    """
    return ResourceTransferMutation(
        from_target=EntityTarget.ACTOR, to_target=EntityTarget.ACTOR_COLLECTIVE, resources=resources
    )


def collectiveWithdraw(resources: dict[str, int]) -> ResourceTransferMutation:
    """Mutation: transfer resources from actor's collective to actor.

    Args:
        resources: Map of resource name to amount. Use -1 for "all available".
    """
    return ResourceTransferMutation(
        from_target=EntityTarget.ACTOR_COLLECTIVE, to_target=EntityTarget.ACTOR, resources=resources
    )


def updateTarget(deltas: dict[str, int]) -> ResourceDeltaMutation:
    """Mutation: apply resource deltas to target.

    Args:
        deltas: Map of resource name to delta (positive = gain, negative = lose).
    """
    return ResourceDeltaMutation(target=EntityTarget.TARGET, deltas=deltas)


def updateActor(deltas: dict[str, int]) -> ResourceDeltaMutation:
    """Mutation: apply resource deltas to actor.

    Args:
        deltas: Map of resource name to delta (positive = gain, negative = lose).
    """
    return ResourceDeltaMutation(target=EntityTarget.ACTOR, deltas=deltas)


def updateTargetCollective(deltas: dict[str, int]) -> ResourceDeltaMutation:
    """Mutation: apply resource deltas to target's collective.

    Args:
        deltas: Map of resource name to delta (positive = gain, negative = lose).
    """
    return ResourceDeltaMutation(target=EntityTarget.TARGET_COLLECTIVE, deltas=deltas)


def updateActorCollective(deltas: dict[str, int]) -> ResourceDeltaMutation:
    """Mutation: apply resource deltas to actor's collective.

    Args:
        deltas: Map of resource name to delta (positive = gain, negative = lose).
    """
    return ResourceDeltaMutation(target=EntityTarget.ACTOR_COLLECTIVE, deltas=deltas)
