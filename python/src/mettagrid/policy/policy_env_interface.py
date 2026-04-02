"""Lightweight environment description for policy initialization."""

from __future__ import annotations

import json
from functools import cached_property
from typing import TYPE_CHECKING, Any, Literal, Optional, cast

import gymnasium as gym
import numpy as np
from pydantic import BaseModel, Field

from mettagrid.config.action_config import CHANGE_VIBE_PREFIX
from mettagrid.config.id_map import ObservationFeatureSpec
from mettagrid.config.mettagrid_config import MettaGridConfig, TalkConfig
from mettagrid.mettagrid_c import dtype_observations

if TYPE_CHECKING:
    from mettagrid.protobuf.sim.policy_v1 import policy_pb2


class PolicyEnvInterface(BaseModel):
    obs_features: list[ObservationFeatureSpec] = Field(
        default_factory=list,
        description="Feature specs (id, name, normalization) for parsing token-based observations. "
        "Each token has a feature ID that maps to a spec.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Alphabetically-sorted list of object tags (e.g., 'agent', 'wall', 'chest'). "
        "Tag IDs in observations are indices into this list.",
    )
    action_names: list[str] = Field(
        description="Ordered list of primary action names. "
        "Action indices in policy outputs correspond to this primary action space."
    )
    vibe_action_names: list[str] = Field(default_factory=list, description="Action names for vibe-only actions.")
    move_energy_cost: Optional[int] = Field(
        default=None,
        description="Energy cost for a single move action, if configured.",
    )
    observation_kind: Literal["token", "box", "bitmask"] = Field(
        default="token",
        description="Whether env_obs contains token observations, bitmask observations, or raw box observations.",
    )
    observation_dtype: str = Field(
        default=dtype_observations.name,
        description="NumPy dtype name for the observation tensor.",
    )
    observation_low: float | None = Field(
        default=0.0,
        description="Scalar lower bound for Box observation spaces when available.",
    )
    observation_high: float | None = Field(
        default=255.0,
        description="Scalar upper bound for Box observation spaces when available.",
    )
    num_agents: int = Field(description="Number of agents in the environment.")
    observation_shape: tuple[int, ...] = Field(
        description="Shape of the observation tensor, typically (num_tokens, token_dim)."
    )
    egocentric_shape: tuple[int, int] = Field(
        description="(height, width) of the egocentric observation window in grid cells. "
        "Agents observe a rectangular region centered on themselves."
    )
    talk: TalkConfig = Field(
        default_factory=TalkConfig,
        description="Talk sidecar configuration exposed to policies.",
    )

    @property
    def obs_height(self) -> int:
        """Height of the egocentric observation window."""
        return self.egocentric_shape[0]

    @property
    def obs_width(self) -> int:
        """Width of the egocentric observation window."""
        return self.egocentric_shape[1]

    @property
    def observation_space(self) -> gym.spaces.Box:
        """Observation space derived from observation_shape."""
        dtype = np.dtype(self.observation_dtype)
        low = 0.0 if self.observation_low is None else float(self.observation_low)
        high = 255.0 if self.observation_high is None else float(self.observation_high)
        return gym.spaces.Box(low, high, self.observation_shape, dtype=dtype.type)

    @property
    def action_space(self) -> gym.spaces.Discrete:
        """Primary action space derived from action_names."""
        return gym.spaces.Discrete(len(self.action_names))

    @property
    def vibe_action_space(self) -> gym.spaces.Discrete:
        """Action space derived from vibe actions."""
        num_vibe_actions = len(self.vibe_action_names)
        if num_vibe_actions <= 0:
            return gym.spaces.Discrete(1)
        return gym.spaces.Discrete(num_vibe_actions)

    @staticmethod
    def _split_action_names(action_names: list[str]) -> tuple[list[str], list[str]]:
        primary_action_names: list[str] = []
        vibe_action_names: list[str] = []
        for action_name in action_names:
            is_vibe_action = action_name.startswith(CHANGE_VIBE_PREFIX)
            if is_vibe_action:
                vibe_action_names.append(action_name)
            else:
                primary_action_names.append(action_name)
        return primary_action_names, vibe_action_names

    @cached_property
    def all_action_names(self) -> list[str]:
        """Canonical flat list: [*primary_actions, *vibe_actions]."""
        return [*self.action_names, *self.vibe_action_names]

    @cached_property
    def action_name_to_flat_index(self) -> dict[str, int]:
        """Canonical mapping from action name to flat index in [0, N_primary + N_vibe)."""
        return {name: idx for idx, name in enumerate(self.all_action_names)}

    @property
    def tag_id_to_name(self) -> dict[int, str]:
        """Tag ID to name mapping, derived from alphabetically-sorted tags list."""
        return {i: name for i, name in enumerate(self.tags)}

    @classmethod
    def from_mg_cfg(cls, mg_cfg: MettaGridConfig) -> "PolicyEnvInterface":
        """Create PolicyEnvInterface from MettaGridConfig.

        Args:
            mg_cfg: The MettaGrid configuration

        Returns:
            A PolicyEnvInterface instance with environment information
        """
        id_map = mg_cfg.game.id_map()
        tag_names_list = id_map.tag_names()
        actions_list = mg_cfg.game.actions.actions()
        action_names = [a.name for a in actions_list]
        primary_action_names, vibe_action_names = cls._split_action_names(action_names)
        move_energy_cost = None
        if mg_cfg.game.actions.move and mg_cfg.game.actions.move.consumed_resources:
            move_energy_cost = mg_cfg.game.actions.move.consumed_resources.get("energy")

        return PolicyEnvInterface(
            obs_features=id_map.features(),
            tags=tag_names_list,
            action_names=primary_action_names,
            vibe_action_names=vibe_action_names,
            num_agents=mg_cfg.game.num_agents,
            observation_shape=(mg_cfg.game.obs.num_tokens, mg_cfg.game.obs.token_dim),
            egocentric_shape=(mg_cfg.game.obs.height, mg_cfg.game.obs.width),
            move_energy_cost=move_energy_cost,
            talk=mg_cfg.game.talk.model_copy(deep=True),
            observation_kind="token",
            observation_dtype=dtype_observations.name,
            observation_low=0.0,
            observation_high=255.0,
        )

    @classmethod
    def from_spaces(
        cls,
        *,
        observation_space: gym.Space[Any],
        action_space: gym.Space[Any],
        num_agents: int,
        action_names: list[str] | None = None,
        vibe_action_names: list[str] | None = None,
    ) -> "PolicyEnvInterface":
        """Create PolicyEnvInterface from generic Gymnasium spaces."""
        if not isinstance(observation_space, gym.spaces.Box):
            raise TypeError(
                "PolicyEnvInterface.from_spaces requires a gymnasium.spaces.Box observation space, "
                f"got {type(observation_space).__name__}"
            )
        if not isinstance(action_space, gym.spaces.Discrete):
            raise TypeError(
                "PolicyEnvInterface.from_spaces requires a gymnasium.spaces.Discrete action space, "
                f"got {type(action_space).__name__}"
            )

        obs_shape = tuple(int(dim) for dim in observation_space.shape)
        if not obs_shape:
            raise ValueError("External observation spaces must have at least one dimension")
        if len(obs_shape) == 1:
            egocentric_shape = (1, obs_shape[0])
        else:
            egocentric_shape = (obs_shape[-2], obs_shape[-1])

        if action_names is None:
            action_names = [f"action_{idx}" for idx in range(int(action_space.n))]
        if len(action_names) != int(action_space.n):
            raise ValueError(
                "External action_names length must match the action space size, "
                f"got len(action_names)={len(action_names)} action_space.n={int(action_space.n)}"
            )
        vibe_action_names = list(vibe_action_names or [])

        low = observation_space.low
        high = observation_space.high
        scalar_low = float(np.min(low)) if np.isfinite(low).all() else None
        scalar_high = float(np.max(high)) if np.isfinite(high).all() else None

        return cls(
            action_names=list(action_names),
            vibe_action_names=vibe_action_names,
            num_agents=int(num_agents),
            observation_shape=obs_shape,
            egocentric_shape=egocentric_shape,
            observation_kind="box",
            observation_dtype=np.dtype(observation_space.dtype).name,
            observation_low=scalar_low,
            observation_high=scalar_high,
        )

    def to_json(self) -> str:
        """Convert PolicyEnvInterface to JSON."""
        # TODO: Andre: replace this with `.model_dump(mode="json")`, now that it supports all fields
        payload = self.model_dump(mode="json", include={"num_agents", "tags", "talk"})
        payload["obs_width"] = self.obs_width
        payload["obs_height"] = self.obs_height
        payload["actions"] = self.all_action_names
        payload["vibe_action_names"] = self.vibe_action_names
        payload["obs_features"] = [feature.model_dump(mode="json") for feature in self.obs_features]
        payload["observation_kind"] = self.observation_kind
        payload["observation_dtype"] = self.observation_dtype
        payload["observation_low"] = self.observation_low
        payload["observation_high"] = self.observation_high
        return json.dumps(payload)

    def to_proto(self) -> "policy_pb2.PolicyEnvInterface":
        """Convert to protobuf PolicyEnvInterface message."""
        from mettagrid.protobuf.sim.policy_v1 import policy_pb2  # noqa: PLC0415

        proto = policy_pb2.PolicyEnvInterface(
            obs_features=[
                policy_pb2.GameRules.Feature(id=f.id, name=f.name, normalization=f.normalization)
                for f in self.obs_features
            ],
            tags=list(self.tags),
            action_names=self.all_action_names,
            move_energy_cost=self.move_energy_cost if self.move_energy_cost is not None else -1,
            num_agents=self.num_agents,
            observation_shape=list(self.observation_shape),
            obs_height=self.obs_height,
            obs_width=self.obs_width,
        )
        if self.talk.enabled:
            proto.talk.CopyFrom(
                policy_pb2.TalkConfig(
                    max_length=self.talk.max_length,
                    cooldown_steps=self.talk.cooldown_steps,
                )
            )
        return proto

    @staticmethod
    def from_proto(proto: "policy_pb2.PolicyEnvInterface") -> "PolicyEnvInterface":
        """Create PolicyEnvInterface from protobuf message."""
        proto_as_any = cast(Any, proto)
        primary_action_names, vibe_action_names = PolicyEnvInterface._split_action_names(
            list(proto_as_any.action_names)
        )

        return PolicyEnvInterface(
            obs_features=[
                ObservationFeatureSpec(
                    id=f.id,
                    name=f.name,
                    normalization=f.normalization,
                )
                for f in proto_as_any.obs_features
            ],
            tags=list(proto_as_any.tags),
            action_names=primary_action_names,
            vibe_action_names=vibe_action_names,
            move_energy_cost=proto_as_any.move_energy_cost if proto_as_any.move_energy_cost != -1 else None,
            num_agents=proto_as_any.num_agents,
            observation_shape=tuple(proto_as_any.observation_shape),
            egocentric_shape=(proto_as_any.obs_height, proto_as_any.obs_width),
            talk=(
                TalkConfig(
                    enabled=True,
                    max_length=proto_as_any.talk.max_length,
                    cooldown_steps=proto_as_any.talk.cooldown_steps,
                )
                if proto_as_any.HasField("talk")
                else TalkConfig()
            ),
            observation_kind="token",
            observation_dtype=dtype_observations.name,
            observation_low=0.0,
            observation_high=255.0,
        )
