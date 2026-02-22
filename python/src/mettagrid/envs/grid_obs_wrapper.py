"""Env wrapper that converts sparse token observations to dense spatial grids.

Wraps a MettaGridPufferEnv so that observations become (num_agents, C, H, W) float32
arrays, directly usable with CNNs:

    env = MettaGridPufferEnv(simulator, cfg, seed=42)
    env = GridObsWrapper(env)  # obs are now (num_agents, num_features, H, W) float32
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np
from gymnasium.spaces import Box

from mettagrid.envs.mettagrid_puffer_env import MettaGridPufferEnv
from mettagrid.policy.policy_env_interface import PolicyEnvInterface

_PADDING = 0xFF
_GLOBAL = 0xFE


class GridObsWrapper:
    """Converts sparse token observations to dense (C, H, W) grids per agent.

    Token format: each token is [coord_byte, feature_id, value].
    - coord_byte encodes (y, x) as nibbles: y = high nibble, x = low nibble
    - 0xFF = padding (ignored)
    - 0xFE = global token (placed at grid center)
    """

    def __init__(self, env: MettaGridPufferEnv):
        self._env = env
        pei = PolicyEnvInterface.from_mg_cfg(env.env_cfg)

        self._obs_height = pei.obs_height
        self._obs_width = pei.obs_width
        self._num_features = max((int(f.id) for f in pei.obs_features), default=0) + 1

        # Pre-compute per-feature normalization scale (indexed by feature id)
        scale = np.ones(max(256, self._num_features), dtype=np.float32)
        for f in pei.obs_features:
            scale[f.id] = max(float(f.normalization), 1.0)
        self._scale = scale

        self._center_y = self._obs_height // 2
        self._center_x = self._obs_width // 2

        self.single_observation_space = Box(
            low=0.0,
            high=np.inf,
            shape=(self._num_features, self._obs_height, self._obs_width),
            dtype=np.float32,
        )

    def _convert(self, raw_obs: np.ndarray) -> np.ndarray:
        """Convert (num_agents, num_tokens, 3) uint8 tokens to (num_agents, C, H, W) float32."""
        n_agents = raw_obs.shape[0]
        H, W, C = self._obs_height, self._obs_width, self._num_features

        grid = np.zeros((n_agents, C, H, W), dtype=np.float32)

        coord_bytes = raw_obs[..., 0]  # (N, T)
        feature_ids = raw_obs[..., 1].astype(np.int32)  # (N, T)
        values = raw_obs[..., 2].astype(np.float32)  # (N, T)

        # Decode nibble coordinates
        y_coords = (coord_bytes >> 4) & 0x0F
        x_coords = coord_bytes & 0x0F

        # Global tokens go to center cell
        global_mask = coord_bytes == _GLOBAL
        y_coords = np.where(global_mask, self._center_y, y_coords)
        x_coords = np.where(global_mask, self._center_x, x_coords)

        # Valid = not padding, coords in bounds, feature id in range
        valid = (coord_bytes != _PADDING) & (y_coords < H) & (x_coords < W) & (feature_ids < C) & (feature_ids >= 0)

        # Normalize values (invalid tokens get zeroed by valid mask)
        clamped_fids = np.clip(feature_ids, 0, self._scale.shape[0] - 1)
        values = (values / self._scale[clamped_fids]) * valid

        # Clamp all indices so np.add.at doesn't go out of bounds.
        # Invalid tokens have value=0 from the mask above, so clamped indices are harmless.
        safe_fids = np.clip(feature_ids, 0, C - 1)
        safe_y = np.clip(y_coords, 0, H - 1).astype(np.intp)
        safe_x = np.clip(x_coords, 0, W - 1).astype(np.intp)

        # Scatter into grid using np.add.at
        agent_idx = np.broadcast_to(np.arange(n_agents)[:, None], coord_bytes.shape)
        np.add.at(grid, (agent_idx, safe_fids, safe_y, safe_x), values)

        return grid

    def reset(self, seed: Optional[int] = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        raw_obs, info = self._env.reset(seed=seed)
        return self._convert(raw_obs), info

    def step(self, actions: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict[str, Any]]:
        raw_obs, rewards, terminals, truncations, info = self._env.step(actions)
        return self._convert(raw_obs), rewards, terminals, truncations, info

    @property
    def num_agents(self) -> int:
        return self._env.num_agents

    @property
    def single_action_space(self):
        return self._env.single_action_space

    @property
    def env_cfg(self):
        return self._env.env_cfg

    def close(self) -> None:
        self._env.close()

    def render(self) -> str:
        return self._env.render()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._env, name)
