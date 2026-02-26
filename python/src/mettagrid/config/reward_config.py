"""Reward configuration for agents."""

from pydantic import Field

from mettagrid.base_config import Config
from mettagrid.config.game_value import (
    AnyGameValue,
    ConstValue,
    InventoryValue,
    MaxGameValue,
    MinGameValue,
    QueryCountValue,
    QueryInventoryValue,
    RatioGameValue,
    StatValue,
    SumGameValue,
    val,
    weighted_sum,
)


class AgentReward(Config):
    """Reward computed from a single game value expression."""

    reward: AnyGameValue = Field(default_factory=lambda: val(0.0))
    per_tick: bool = False  # Accumulate value each tick instead of delta at end of episode


# ===== Helper functions for concise reward definitions =====


def reward(
    value: AnyGameValue | list[AnyGameValue],
    *,
    weight: float = 1.0,
    log: bool = False,
    min: int | float | None = None,
    max: int | float | None = None,
    per_tick: bool = False,
) -> AgentReward:
    """Create an AgentReward from one or more game values."""
    values = value if isinstance(value, list) else [value]
    return AgentReward(
        reward=weighted_sum([(weight, v) for v in values], log=log, min=min, max=max),
        per_tick=per_tick,
    )


def inventoryReward(
    item: str,
    *,
    weight: float = 1.0,
    max: int | float | None = None,
    per_tick: bool = False,
) -> AgentReward:
    """Create an AgentReward from an inventory item count."""
    return reward(InventoryValue(item=item), weight=weight, max=max, per_tick=per_tick)


AgentReward.model_rebuild(
    _types_namespace={
        "AnyGameValue": AnyGameValue,
        "InventoryValue": InventoryValue,
        "StatValue": StatValue,
        "ConstValue": ConstValue,
        "QueryInventoryValue": QueryInventoryValue,
        "QueryCountValue": QueryCountValue,
        "SumGameValue": SumGameValue,
        "RatioGameValue": RatioGameValue,
        "MaxGameValue": MaxGameValue,
        "MinGameValue": MinGameValue,
    }
)
