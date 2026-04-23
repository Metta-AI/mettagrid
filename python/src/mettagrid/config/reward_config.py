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

    @classmethod
    def default_for_key(cls, key: str) -> "AgentReward":
        return reward(InventoryValue(item=key))

    @property
    def weight(self) -> float:
        game_value = self.reward.values[0] if isinstance(self.reward, MinGameValue) else self.reward
        assert isinstance(game_value, SumGameValue)
        assert game_value.weights is not None
        return game_value.weights[0]

    @weight.setter
    def weight(self, value: int | float) -> None:
        game_value = self.reward.values[0] if isinstance(self.reward, MinGameValue) else self.reward
        assert isinstance(game_value, SumGameValue)
        assert game_value.weights is not None
        game_value.weights[0] = float(value)

    @property
    def max(self) -> float | None:
        if isinstance(self.reward, MinGameValue):
            max_value = self.reward.values[1]
            assert isinstance(max_value, ConstValue)
            return max_value.value
        return None

    @max.setter
    def max(self, value: int | float | None) -> None:
        if isinstance(self.reward, MinGameValue):
            if value is None:
                self.reward = self.reward.values[0]
            else:
                self.reward.values[1] = val(value)
        elif value is not None:
            self.reward = MinGameValue(values=[self.reward, val(value)])


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
