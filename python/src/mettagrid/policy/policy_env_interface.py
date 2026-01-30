"""Lightweight environment description for policy initialization."""

import json
from typing import Optional

import gymnasium as gym
from pydantic import BaseModel, Field

from mettagrid.config.id_map import ObservationFeatureSpec
from mettagrid.config.mettagrid_config import MettaGridConfig
from mettagrid.mettagrid_c import dtype_observations


class PolicyEnvInterface(BaseModel):
    obs_features: list[ObservationFeatureSpec] = Field(
        description="Feature specs (id, name, normalization) for parsing token-based observations. "
        "Each token has a feature ID that maps to a spec."
    )
    tags: list[str] = Field(
        description="Alphabetically-sorted list of object tags (e.g., 'agent', 'wall', 'chest'). "
        "Tag IDs in observations are indices into this list."
    )
    action_names: list[str] = Field(
        description="Ordered list of action names (e.g., ['noop', 'move_north', ...]). "
        "Action indices in the policy output correspond to this list."
    )
    move_energy_cost: Optional[int] = Field(
        default=None,
        description="Energy cost for a single move action, if configured.",
    )
    num_agents: int = Field(description="Number of agents in the environment.")
    observation_shape: tuple[int, ...] = Field(
        description="Shape of the observation tensor, typically (num_tokens, token_dim)."
    )
    egocentric_shape: tuple[int, int] = Field(
        description="(height, width) of the egocentric observation window in grid cells. "
        "Agents observe a rectangular region centered on themselves."
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
        return gym.spaces.Box(0, 255, self.observation_shape, dtype=dtype_observations.type)

    @property
    def action_space(self) -> gym.spaces.Discrete:
        """Action space derived from action_names."""
        return gym.spaces.Discrete(len(self.action_names))

    @property
    def tag_id_to_name(self) -> dict[int, str]:
        """Tag ID to name mapping, derived from alphabetically-sorted tags list."""
        return {i: name for i, name in enumerate(self.tags)}

    @staticmethod
    def from_mg_cfg(mg_cfg: MettaGridConfig) -> "PolicyEnvInterface":
        """Create PolicyEnvInterface from MettaGridConfig.

        Args:
            mg_cfg: The MettaGrid configuration

        Returns:
            A PolicyEnvInterface instance with environment information
        """
        id_map = mg_cfg.game.id_map()
        tag_names_list = id_map.tag_names()
        actions_list = mg_cfg.game.actions.actions()
        move_energy_cost = None
        if mg_cfg.game.actions.move and mg_cfg.game.actions.move.consumed_resources:
            move_energy_cost = mg_cfg.game.actions.move.consumed_resources.get("energy")

        return PolicyEnvInterface(
            obs_features=id_map.features(),
            tags=tag_names_list,
            action_names=[a.name for a in actions_list],
            num_agents=mg_cfg.game.num_agents,
            observation_shape=(mg_cfg.game.obs.num_tokens, mg_cfg.game.obs.token_dim),
            egocentric_shape=(mg_cfg.game.obs.height, mg_cfg.game.obs.width),
            move_energy_cost=move_energy_cost,
        )

    def to_json(self) -> str:
        """Convert PolicyEnvInterface to JSON."""
        # TODO: Andre: replace this with `.model_dump(mode="json")`, now that it supports all fields
        payload = self.model_dump(mode="json", include={"num_agents", "tags"})
        payload["obs_width"] = self.obs_width
        payload["obs_height"] = self.obs_height
        payload["actions"] = self.action_names
        payload["obs_features"] = [feature.model_dump(mode="json") for feature in self.obs_features]
        return json.dumps(payload)
