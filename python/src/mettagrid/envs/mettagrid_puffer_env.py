"""
MettaGridPufferEnv - PufferLib integration for MettaGrid.

This class provides PufferLib compatibility for MettaGrid environments using
the Simulation class. This allows MettaGrid environments to be used
directly with PufferLib training infrastructure.

Provides:
 - Auto-reset on episode completion
 - Persistent buffers for re-use between resets

Architecture:
- MettaGridPufferEnv wraps Simulation and provides PufferEnv interface
- This enables MettaGridPufferEnv to work seamlessly with PufferLib training code

For users:
- Use MettaGridPufferEnv directly with PufferLib (it inherits PufferLib functionality)
- Alternatively, use PufferLib's MettaPuff wrapper for additional PufferLib features:
  https://github.com/PufferAI/PufferLib/blob/main/pufferlib/environments/metta/environment.py

This avoids double-wrapping while maintaining full PufferLib compatibility.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np
from gymnasium.spaces import Box, Discrete
from typing_extensions import override

from mettagrid.config.mettagrid_config import MettaGridConfig
from mettagrid.mettagrid_c import (
    dtype_actions,
    dtype_masks,
    dtype_observations,
    dtype_rewards,
    dtype_terminals,
    dtype_truncations,
)
from mettagrid.policy.loader import initialize_or_load_policy
from mettagrid.policy.policy import MultiAgentPolicy, PolicySpec
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.policy.supervisor_actions import split_supervisor_actions_inplace
from mettagrid.simulator import Simulation, Simulator
from mettagrid.simulator.simulator import Buffers
from pufferlib.pufferlib import PufferEnv  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

# Type compatibility assertions - ensure C++ types match PufferLib expectations
# PufferLib expects particular datatypes - see pufferlib/vector.py
assert dtype_observations == np.dtype(np.uint8)
assert dtype_terminals == np.dtype(np.bool_)
assert dtype_truncations == np.dtype(np.bool_)
assert dtype_rewards == np.dtype(np.float32)
assert dtype_actions == np.dtype(np.int32)


class MettaGridPufferEnv(PufferEnv):
    """
    Wraps the Simulator class to provide PufferLib compatibility.

    Inherits from pufferlib.PufferEnv: High-performance vectorized environment interface
      https://github.com/PufferAI/PufferLib/blob/main/pufferlib/environments.py
    """

    metadata = {"render_modes": ["ansi"]}

    def __init__(
        self,
        simulator: Simulator,
        cfg: MettaGridConfig,
        supervisor_policy_spec: Optional[PolicySpec] = None,
        step_info_keys: Optional[Sequence[str]] = None,
        buf: Any = None,
        seed: int = 0,
    ):
        # Support both Simulation and MettaGridConfig for backwards compatibility
        self._simulator = simulator
        self._current_cfg = cfg
        self._current_seed = seed
        self._supervisor_policy_spec = supervisor_policy_spec
        self._policy_env_info = PolicyEnvInterface.from_mg_cfg(cfg)
        self._env_supervisor: MultiAgentPolicy | None = None
        self._supervisor_uses_vibe_action_space = bool(self._policy_env_info.vibe_action_names)
        self._supervisor_action_ids: np.ndarray | None = None
        self._vibe_action_ids_by_index: np.ndarray | None = None

        # Initialize shared buffers FIRST (before super().__init__)
        # because PufferLib may access them during initialization

        self._buffers: Buffers = Buffers(
            observations=np.zeros(
                (self._policy_env_info.num_agents, *self._policy_env_info.observation_space.shape),
                dtype=dtype_observations,
            ),
            terminals=np.zeros(self._policy_env_info.num_agents, dtype=dtype_terminals),
            truncations=np.zeros(self._policy_env_info.num_agents, dtype=dtype_truncations),
            rewards=np.zeros(self._policy_env_info.num_agents, dtype=dtype_rewards),
            masks=np.ones(self._policy_env_info.num_agents, dtype=dtype_masks),
            actions=np.zeros(self._policy_env_info.num_agents, dtype=dtype_actions),
            vibe_actions=np.zeros(self._policy_env_info.num_agents, dtype=dtype_actions),
            teacher_actions=np.zeros(self._policy_env_info.num_agents, dtype=dtype_actions),
        )

        # Set observation and action spaces BEFORE calling super().__init__()
        # PufferLib requires these to be set first
        self.single_observation_space: Box = self._policy_env_info.observation_space
        self.single_action_space: Discrete = self._policy_env_info.action_space
        self.single_vibe_action_space: Discrete = self._policy_env_info.vibe_action_space

        self._sim: Optional[Simulation] = None
        self._sim = self._init_simulation()
        self.num_agents = self._sim.num_agents
        self._step_info_game_keys: tuple[tuple[str, str], ...] = ()
        self._step_info_collective_keys: tuple[tuple[str, str, str], ...] = ()
        self._step_info_attribute_keys: tuple[tuple[str, str], ...] = ()
        self._step_info_agent_keys: tuple[str, ...] = ()
        self._configure_step_info_keys(step_info_keys)

        super().__init__(buf=buf)

    def _configure_step_info_keys(self, step_info_keys: Optional[Sequence[str]]) -> None:
        if not step_info_keys:
            return

        game_keys: list[tuple[str, str]] = []
        collective_keys: list[tuple[str, str, str]] = []
        attribute_keys: list[tuple[str, str]] = []
        agent_keys: list[str] = []

        for key in step_info_keys:
            key_str = str(key)
            if key_str.startswith("agent/"):
                agent_key = key_str[len("agent/") :]
                if not agent_key:
                    raise ValueError("step_info_keys contains invalid entry 'agent/' (missing key suffix)")
                agent_keys.append(agent_key)
                continue

            raw = key_str[len("env_") :] if key_str.startswith("env_") else key_str
            if raw.startswith("game/"):
                stat_key = raw[len("game/") :]
                if not stat_key:
                    raise ValueError("step_info_keys contains invalid entry 'game/' (missing key suffix)")
                game_keys.append((raw, stat_key))
                continue

            if raw.startswith("collective/"):
                remainder = raw[len("collective/") :]
                if "/" not in remainder:
                    raise ValueError(
                        "step_info_keys contains invalid collective entry "
                        f"{key_str!r}; expected 'collective/<name>/<stat>'"
                    )
                collective_name, stat_key = remainder.split("/", 1)
                if not collective_name or not stat_key:
                    raise ValueError(
                        "step_info_keys contains invalid collective entry "
                        f"{key_str!r}; expected 'collective/<name>/<stat>'"
                    )
                collective_keys.append((raw, collective_name, stat_key))
                continue

            if raw.startswith("attributes/"):
                attr_key = raw[len("attributes/") :]
                if not attr_key:
                    raise ValueError("step_info_keys contains invalid entry 'attributes/' (missing key suffix)")
                attribute_keys.append((raw, attr_key))
                continue

            raise ValueError(
                f"Unsupported step_info_keys entry {key_str!r}; expected 'game/...', 'collective/...', "
                "'attributes/...', or 'agent/...'."
            )

        # Preserve order for determinism (useful for debugging), but drop duplicates.
        self._step_info_game_keys = tuple(dict.fromkeys(game_keys))
        self._step_info_collective_keys = tuple(dict.fromkeys(collective_keys))
        self._step_info_attribute_keys = tuple(dict.fromkeys(attribute_keys))
        self._step_info_agent_keys = tuple(dict.fromkeys(agent_keys))

    @property
    def env_cfg(self) -> MettaGridConfig:
        """Get the environment configuration."""
        return self._current_cfg

    def set_mg_config(self, config: MettaGridConfig) -> None:
        self._current_cfg = config

    def get_episode_rewards(self) -> np.ndarray:
        sim = self._sim
        assert sim is not None
        return sim.episode_rewards

    @property
    def current_simulation(self) -> Simulation:
        if self._sim is None:
            raise RuntimeError("Simulation is closed")
        return self._sim

    def _init_simulation(self) -> Simulation:
        sim = self._simulator.new_simulation(self._current_cfg, self._current_seed, buffers=self._buffers)
        if self._policy_env_info.vibe_action_names:
            self._vibe_action_ids_by_index = np.array(
                [sim.action_ids[action_name] for action_name in self._policy_env_info.vibe_action_names],
                dtype=dtype_actions,
            )
        else:
            self._vibe_action_ids_by_index = np.zeros((0,), dtype=dtype_actions)
        if self._supervisor_policy_spec is not None:
            supervisor_env_info = self._supervisor_policy_env_info()

            self._supervisor_uses_vibe_action_space = bool(supervisor_env_info.vibe_action_names)
            self._env_supervisor = initialize_or_load_policy(
                supervisor_env_info,
                self._supervisor_policy_spec,
            )
            if self._supervisor_uses_vibe_action_space:
                self._supervisor_action_ids = np.array(
                    [sim.action_ids[action_name] for action_name in supervisor_env_info.action_names],
                    dtype=dtype_actions,
                )
            else:
                self._supervisor_action_ids = None
            self._compute_supervisor_actions()
        return sim

    def _supervisor_policy_env_info(self) -> PolicyEnvInterface:
        return self._policy_env_info

    def _new_sim(self) -> None:
        if self._sim is not None:
            self._sim.close()
        self._sim = self._init_simulation()

    def _build_step_info_payload(self, sim: Simulation) -> dict[str, Any]:
        base_info = sim._context.get("infos", {})
        info_payload = dict(base_info) if isinstance(base_info, dict) else {}

        if not (self._step_info_game_keys or self._step_info_collective_keys or self._step_info_attribute_keys):
            if not self._step_info_agent_keys:
                return info_payload

        c_sim = sim._c_sim

        for raw_key, stat_key in self._step_info_game_keys:
            value = c_sim.get_game_stat(stat_key)
            if value is not None:
                info_payload[raw_key] = float(value)

        for raw_key, collective_name, stat_key in self._step_info_collective_keys:
            value = c_sim.get_collective_stat(collective_name, stat_key)
            if value is not None:
                info_payload[raw_key] = float(value)

        if self._step_info_attribute_keys:
            for raw_key, attr_key in self._step_info_attribute_keys:
                if attr_key == "seed":
                    info_payload[raw_key] = float(sim.seed)
                elif attr_key == "map_w":
                    info_payload[raw_key] = float(sim.map_width)
                elif attr_key == "map_h":
                    info_payload[raw_key] = float(sim.map_height)
                elif attr_key == "steps":
                    info_payload[raw_key] = float(sim.current_step)
                elif attr_key == "max_steps":
                    info_payload[raw_key] = float(getattr(c_sim, "max_steps", sim.config.game.max_steps))
                else:
                    raise ValueError(
                        f"Unsupported step_info_keys attribute {raw_key!r}. "
                        "Supported: seed, map_w, map_h, steps, max_steps."
                    )

        if self._step_info_agent_keys:
            per_agent_infos: dict[int, dict[str, Any]] = {}
            step_rewards = self._buffers.rewards
            episode_rewards = sim.episode_rewards

            for agent_idx in range(self.num_agents):
                row: dict[str, Any] = {}
                for agent_key in self._step_info_agent_keys:
                    if agent_key == "reward_step":
                        row[agent_key] = float(step_rewards[agent_idx])
                    elif agent_key == "reward_episode":
                        row[agent_key] = float(episode_rewards[agent_idx])
                    else:
                        value = c_sim.get_agent_stat(agent_idx, agent_key)
                        if value is not None:
                            row[agent_key] = float(value)
                per_agent_infos[agent_idx] = row

            info_payload["_per_agent_infos"] = per_agent_infos

        return info_payload

    @override
    def reset(self, seed: Optional[int] = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        if seed is not None:
            self._current_seed = seed

        self._new_sim()
        sim = self._sim
        assert sim is not None

        return self._buffers.observations, self._build_step_info_payload(sim)

    @override
    def step(self, actions: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict[str, Any]]:
        sim = self._sim
        assert sim is not None
        if sim._c_sim.terminals().all() or sim._c_sim.truncations().all():
            self._new_sim()
            sim = self._sim
            assert sim is not None

        # Gymnasium returns int64 arrays by default when sampling MultiDiscrete spaces,
        # so coerce here to keep callers simple while preserving strict bounds checking.
        actions_view = actions if actions.dtype == dtype_actions else np.asarray(actions, dtype=dtype_actions)
        core_actions = actions_view
        learner_vibe_actions: Optional[np.ndarray] = None
        num_non_vibe_actions = int(self.single_action_space.n)
        num_vibe_actions = len(self._policy_env_info.vibe_action_names)
        vibe_action_ids_by_index = self._vibe_action_ids_by_index
        if num_non_vibe_actions <= 0:
            raise ValueError("Environment must expose at least one non-vibe action")
        if actions_view.ndim == 2:
            if actions_view.shape[1] == 1:
                core_actions = actions_view[:, 0]
            elif actions_view.shape[1] == 2:
                core_actions = actions_view[:, 0]
                raw_vibe = actions_view[:, 1].astype(np.int64, copy=False)
                if bool((raw_vibe < 0).any()):
                    raise ValueError(f"Vibe actions must be non-negative, got min={raw_vibe.min()}")
                if num_vibe_actions > 0 and bool((raw_vibe < num_vibe_actions).all()):
                    assert vibe_action_ids_by_index is not None
                    learner_vibe_actions = vibe_action_ids_by_index[raw_vibe]
                else:
                    learner_vibe_actions = raw_vibe.astype(dtype_actions, copy=False)
            else:
                raise ValueError(
                    f"Expected step actions shape [num_agents] or [num_agents,2], got {actions_view.shape}"
                )
        elif actions_view.ndim == 1:
            actions_i64 = actions_view.astype(np.int64, copy=False)
            if bool((actions_i64 < 0).any()):
                raise ValueError(f"Core actions must be non-negative, got min={actions_i64.min()}")
            encoded_mask = actions_i64 >= num_non_vibe_actions
            if bool(encoded_mask.any()):
                if num_vibe_actions <= 0:
                    raise ValueError(
                        "Received encoded vibe actions but this environment has no configured vibe action space"
                    )
                vibe_bucket = actions_i64 // num_non_vibe_actions
                core_actions = (actions_i64 % num_non_vibe_actions).astype(dtype_actions, copy=False)
                vibe_indices = vibe_bucket - 1
                if bool((vibe_indices < 0).any()) or bool((vibe_indices >= num_vibe_actions).any()):
                    raise ValueError(
                        f"Encoded vibe action indices out of range [0,{num_vibe_actions}), "
                        f"min={vibe_indices.min()} max={vibe_indices.max()}"
                    )
                assert vibe_action_ids_by_index is not None
                learner_vibe_actions = np.zeros(core_actions.shape, dtype=dtype_actions)
                learner_vibe_actions[encoded_mask] = vibe_action_ids_by_index[vibe_indices[encoded_mask]]
        else:
            raise ValueError(f"Expected step actions shape [num_agents] or [num_agents,2], got {actions_view.shape}")

        core_actions_i64 = core_actions.astype(np.int64, copy=False)
        if bool((core_actions_i64 < 0).any()) or bool((core_actions_i64 >= num_non_vibe_actions).any()):
            raise ValueError(
                f"Core actions out of range [0,{num_non_vibe_actions}), "
                f"min={core_actions_i64.min()} max={core_actions_i64.max()}"
            )
        if core_actions.dtype != dtype_actions:
            core_actions = core_actions.astype(dtype_actions, copy=False)

        if core_actions.shape != self._buffers.actions.shape:
            raise ValueError(f"Expected {self._buffers.actions.shape} core actions, got {core_actions.shape}")
        np.copyto(self._buffers.actions, core_actions, casting="safe")

        vibe_actions = self._buffers.vibe_actions
        if learner_vibe_actions is not None:
            assert vibe_actions is not None
            if learner_vibe_actions.shape != vibe_actions.shape:
                raise ValueError(f"Expected {vibe_actions.shape} vibe actions, got {learner_vibe_actions.shape}")
            np.copyto(vibe_actions, learner_vibe_actions, casting="safe")
        elif self._supervisor_policy_spec is None:
            assert vibe_actions is not None
            vibe_actions.fill(dtype_actions.type(0))

        sim.step()

        # Do this after step() so that the trainer can use it if needed
        if self._supervisor_policy_spec is not None:
            self._compute_supervisor_actions()

        return (
            self._buffers.observations,
            self._buffers.rewards,
            self._buffers.terminals,
            self._buffers.truncations,
            self._build_step_info_payload(sim),
        )

    def _compute_supervisor_actions(self) -> None:
        supervisor = self._env_supervisor
        assert supervisor is not None
        teacher_actions = self._buffers.teacher_actions
        raw_observations = self._buffers.observations
        supervisor.step_batch(raw_observations, teacher_actions)
        vibe_actions = self._buffers.vibe_actions
        assert vibe_actions is not None
        if not self._supervisor_uses_vibe_action_space:
            np.copyto(vibe_actions, teacher_actions)
            return

        supervisor_action_ids = self._supervisor_action_ids
        assert supervisor_action_ids is not None

        split_supervisor_actions_inplace(
            teacher_actions,
            vibe_actions,
            supervisor_action_ids=supervisor_action_ids,
            action_names=[*self._policy_env_info.action_names, *self._policy_env_info.vibe_action_names],
        )

    def disable_supervisor(self) -> None:
        """Disable supervisor policy to avoid extra forward passes after teacher phase."""
        self._supervisor_policy_spec = None
        self._env_supervisor = None

    @property
    def observations(self) -> np.ndarray:
        return self._buffers.observations

    @observations.setter
    def observations(self, observations: np.ndarray) -> None:
        self._buffers.observations = observations

    @property
    def rewards(self) -> np.ndarray:
        return self._buffers.rewards

    @rewards.setter
    def rewards(self, rewards: np.ndarray) -> None:
        self._buffers.rewards = rewards

    @property
    def terminals(self) -> np.ndarray:
        return self._buffers.terminals

    @terminals.setter
    def terminals(self, terminals: np.ndarray) -> None:
        self._buffers.terminals = terminals

    @property
    def truncations(self) -> np.ndarray:
        return self._buffers.truncations

    @truncations.setter
    def truncations(self, truncations: np.ndarray) -> None:
        self._buffers.truncations = truncations

    @property
    def masks(self) -> np.ndarray:
        return self._buffers.masks

    @masks.setter
    def masks(self, masks: np.ndarray) -> None:
        self._buffers.masks = masks

    @property
    def actions(self) -> np.ndarray:
        return self._buffers.actions

    @actions.setter
    def actions(self, actions: np.ndarray) -> None:
        self._buffers.actions = actions

    @property
    def teacher_actions(self) -> np.ndarray:
        return self._buffers.teacher_actions

    @teacher_actions.setter
    def teacher_actions(self, teacher_actions: np.ndarray) -> None:
        np.copyto(self._buffers.teacher_actions, teacher_actions)
        vibe_actions = self._buffers.vibe_actions
        if vibe_actions is not None:
            np.copyto(vibe_actions, teacher_actions)

    @property
    def vibe_actions(self) -> np.ndarray:
        vibe_actions = self._buffers.vibe_actions
        assert vibe_actions is not None
        return vibe_actions

    @vibe_actions.setter
    def vibe_actions(self, vibe_actions: np.ndarray) -> None:
        self._buffers.vibe_actions = vibe_actions

    @property
    def render_mode(self) -> str:
        """PufferLib render mode - returns 'ansi' for text-based rendering."""
        return "ansi"

    def render(self) -> str:
        """Render the current state as unicode text."""
        from mettagrid.renderer.miniscope.buffer import MapBuffer  # noqa: PLC0415
        from mettagrid.renderer.miniscope.symbol import DEFAULT_SYMBOL_MAP  # noqa: PLC0415

        sim = self._sim
        assert sim is not None
        symbol_map = DEFAULT_SYMBOL_MAP.copy()
        for obj in self._current_cfg.game.objects.values():
            if obj.render_name:
                symbol_map[obj.render_name] = obj.render_symbol
            symbol_map[obj.name] = obj.render_symbol

        return MapBuffer(
            symbol_map=symbol_map,
            initial_height=sim.map_height,
            initial_width=sim.map_width,
        ).render_full_map(sim._c_sim.grid_objects())

    def close(self) -> None:
        """Close the environment."""
        if self._sim is None:
            return
        self._sim.close()
        self._sim = None
