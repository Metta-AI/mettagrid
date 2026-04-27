"""Engine-neutral game interface metadata consumed by policies and runners."""

from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import Field, field_validator, model_validator

from mettagrid.base_config import Config

ObservationKind = Literal["token", "box", "bitmask"]
ObservationWireFormat = Literal["dense_tensor", "mettagrid_triplet_v1", "bitworld_packed_4bit"]
ActionKind = Literal["discrete", "bitmask"]
RewardKind = Literal["scalar_per_agent"]


class FeatureSpec(Config):
    id: int = Field(ge=0)
    name: str = Field(min_length=1)
    normalization: float = Field(gt=0)


class ObservationSpec(Config):
    kind: ObservationKind
    wire_format: ObservationWireFormat = "dense_tensor"
    shape: tuple[int, ...]
    dtype: str
    low: float | None = None
    high: float | None = None
    egocentric_shape: tuple[int, int] | None = None
    features: list[FeatureSpec] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @field_validator("shape")
    @classmethod
    def _validate_shape(cls, shape: tuple[int, ...]) -> tuple[int, ...]:
        if not shape:
            raise ValueError("shape must have at least one dimension")
        if any(dim <= 0 for dim in shape):
            raise ValueError(f"shape dimensions must be positive, got {shape}")
        return shape

    @field_validator("egocentric_shape")
    @classmethod
    def _validate_egocentric_shape(cls, shape: tuple[int, int] | None) -> tuple[int, int] | None:
        if shape is not None and any(dim <= 0 for dim in shape):
            raise ValueError(f"egocentric_shape dimensions must be positive, got {shape}")
        return shape

    @field_validator("dtype")
    @classmethod
    def _normalize_dtype(cls, dtype: str) -> str:
        return np.dtype(dtype).name


class ActionSpaceSpec(Config):
    kind: ActionKind
    names: list[str] = Field(min_length=1)
    bit_count: int | None = Field(default=None, ge=1)

    @field_validator("names")
    @classmethod
    def _validate_names(cls, names: list[str]) -> list[str]:
        if any(not name for name in names):
            raise ValueError("action names must be non-empty")
        return names

    @model_validator(mode="after")
    def _validate_action_space(self) -> "ActionSpaceSpec":
        if self.kind == "discrete":
            if self.bit_count is not None:
                raise ValueError("discrete action spaces must not set bit_count")
            return self

        inferred_bit_count = len(self.names)
        if self.bit_count is None:
            self.bit_count = inferred_bit_count
        if self.bit_count != inferred_bit_count:
            raise ValueError(
                "bit_count must match the number of named bitmask buttons; "
                f"got bit_count={self.bit_count} names={inferred_bit_count}"
            )
        return self

    def discrete_action_names(self) -> list[str]:
        if self.kind == "discrete":
            return list(self.names)

        assert self.bit_count is not None
        action_names: list[str] = []
        for mask in range(1 << self.bit_count):
            active_names = [name for bit, name in enumerate(self.names) if mask & (1 << bit)]
            action_names.append("+".join(active_names) if active_names else "none")
        return action_names


class TalkSpec(Config):
    enabled: bool = False
    max_length: int = Field(default=140, ge=1)
    cooldown_steps: int = Field(default=50, ge=0)
    broadcast_resource: str | None = None


class RewardSpec(Config):
    kind: RewardKind = "scalar_per_agent"
    score_key: str | None = None


class GameInterface(Config):
    protocol_version: Literal["game_interface.v1"] = "game_interface.v1"
    engine_id: str = Field(min_length=1)
    game_id: str = Field(min_length=1)
    num_agents: int = Field(ge=1)
    observation: ObservationSpec
    action: ActionSpaceSpec
    vibe_action: ActionSpaceSpec | None = None
    move_energy_cost: int | None = Field(default=None, ge=0)
    reward: RewardSpec = Field(default_factory=RewardSpec)
    talk: TalkSpec = Field(default_factory=TalkSpec)
