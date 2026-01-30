"""Reward configuration for agents.

Provides GameValue types and helper functions for defining rewards.
"""

from pydantic import Field

from mettagrid.base_config import Config
from mettagrid.config.game_value import (
    AnyGameValue,
    InventoryValue,
    NumObjectsValue,
    Scope,
    StatValue,
    TagCountValue,
)


class AgentReward(Config):
    """Reward computed from game values with optional normalization.

    Formula: weight * product(nums) / product(denoms), capped at max.

    Use the helper functions for concise reward definitions:
        statReward("a.b.c", max=10)
        inventoryReward("heart", weight=0.5)
    """

    nums: list[AnyGameValue] = Field(default_factory=list)
    denoms: list[AnyGameValue] = Field(default_factory=list)
    weight: float = 1.0
    max: float | None = None  # Cap on final reward value


# ===== Helper functions for concise reward definitions =====


def reward(
    value: AnyGameValue,
    *,
    weight: float = 1.0,
    max: float | None = None,
    denoms: list[AnyGameValue] | None = None,
) -> AgentReward:
    """Create an AgentReward with a single numerator value.

    For simpler cases, prefer the dedicated helper functions:
        statReward("a.b.c", max=10)
        inventoryReward("heart", weight=0.5)
        numObjectsReward("junction", weight=0.1)
        numTaggedReward("vibe:aligned", weight=0.5)
    """
    return AgentReward(nums=[value], denoms=denoms or [], weight=weight, max=max)


def stat(
    name: str,
    delta: bool = False,
    scope: Scope = Scope.AGENT,
) -> StatValue:
    """Create a StatValue for reward/observation config."""
    return StatValue(name=name, scope=scope, delta=delta)


def inventoryReward(
    item: str,
    *,
    weight: float = 1.0,
    max: float | None = None,
    denoms: list[AnyGameValue] | None = None,
) -> AgentReward:
    """Create an AgentReward from an inventory item count.

    Examples:
        inventoryReward("heart", weight=0.5)
        inventoryReward("ore_red", max=10)
    """
    return AgentReward(nums=[InventoryValue(item=item, scope=Scope.AGENT)], denoms=denoms or [], weight=weight, max=max)


def collectiveInventoryReward(
    item: str,
    *,
    weight: float = 1.0,
    max: float | None = None,
    denoms: list[AnyGameValue] | None = None,
) -> AgentReward:
    """Create an AgentReward from a collective inventory item count.

    Examples:
        collectiveInventoryReward("heart", weight=0.5)
    """
    return AgentReward(
        nums=[InventoryValue(item=item, scope=Scope.COLLECTIVE)], denoms=denoms or [], weight=weight, max=max
    )


def numObjects(object_type: str) -> NumObjectsValue:
    """Count of objects by type for use in denoms.

    Examples:
        statReward("junction.held", denoms=[numObjects("junction")])
    """
    return NumObjectsValue(object_type=object_type)


def numObjectsReward(
    object_type: str,
    *,
    weight: float = 1.0,
    max: float | None = None,
    denoms: list[AnyGameValue] | None = None,
) -> AgentReward:
    """Create an AgentReward from object count.

    Examples:
        numObjectsReward("junction", weight=0.1)
    """
    return AgentReward(nums=[NumObjectsValue(object_type=object_type)], denoms=denoms or [], weight=weight, max=max)


def numTaggedReward(
    tag: str,
    *,
    weight: float = 1.0,
    max: float | None = None,
    denoms: list[AnyGameValue] | None = None,
) -> AgentReward:
    """Create an AgentReward from tagged object count.

    Examples:
        numTaggedReward("vibe:aligned", weight=0.5)
    """
    return AgentReward(nums=[TagCountValue(tag=tag)], denoms=denoms or [], weight=weight, max=max)


def statReward(
    name: str,
    *,
    scope: Scope = Scope.AGENT,
    delta: bool = False,
    weight: float = 1.0,
    max: float | None = None,
    denoms: list[AnyGameValue] | None = None,
) -> AgentReward:
    """Create an AgentReward from a stat name. Shorthand for reward(stat(...)).

    Examples:
        statReward("a.b.c", max=10)
        statReward("junction.held", scope=Scope.COLLECTIVE, denoms=[numObjects("junction")])
    """
    return AgentReward(
        nums=[StatValue(name=name, scope=scope, delta=delta)],
        denoms=denoms or [],
        weight=weight,
        max=max,
    )
