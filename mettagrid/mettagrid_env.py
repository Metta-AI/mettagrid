"""
MettaGrid Environment implementation for Pufferlib.
This module provides environment classes for Metta Grid simulations.
"""

import copy
from typing import List, Optional, Union

import gymnasium as gym
import hydra
import numpy as np
import pufferlib
from omegaconf import DictConfig, ListConfig, OmegaConf

# Import with explicit comment about the pylint disable
from mettagrid.mettagrid_c import MettaGrid  # C extension module
from mettagrid.resolvers import register_resolvers


class MettaGridEnv(pufferlib.PufferEnv, gym.Env):
    """
    Environment class for MettaGrid simulations.

    This class wraps the C++ MettaGrid implementation and provides a gym-compatible
    interface for reinforcement learning.
    """

    # Type hints for attributes defined in the C++ extension to help Pylance
    observations: np.ndarray
    terminals: np.ndarray
    truncations: np.ndarray
    rewards: np.ndarray
    actions: np.ndarray

    def __init__(self, cfg: Union[DictConfig, ListConfig], render_mode: Optional[str], buf=None, **kwargs):
        """
        Initialize a MettaGridEnv.

        Args:
            cfg: provided OmegaConf configuration
            render_mode: Mode for rendering the environment
            buf: Buffer for Pufferlib
            **kwargs: Additional arguments passed to parent classes
        """
        self._render_mode = render_mode
        self._original_cfg = cfg
        self.active_cfg = self._resolve_original_cfg()

        # Setup episode stats
        self._stats = {"steps": 0, "rewards": [], "total_steps": 0, "total_rewards": []}
        self.infos = {}

        self.initialize_episode()
        super().__init__(buf)

    def _insert_stats_into_cfg(self, cfg) -> DictConfig:
        """
        Insert statistics into the provided configuration.

        This method ensures that the stats section exists and populates
        it with current statistics from the environment.

        Args:
            cfg: The configuration to update

        Returns:
            The updated configuration with stats inserted
        """
        # Create stats section if it doesn't exist
        if not hasattr(cfg, "stats"):
            cfg.stats = OmegaConf.create({})

        # Push our stats into the config so that we can use them in the resolvers
        if hasattr(self, "_stats"):
            # Copy all stats into the config
            for key, value in self._stats.items():
                setattr(cfg.stats, key, value)
        else:
            # Initialize with default values if _stats doesn't exist yet
            cfg.stats.steps = 0
            cfg.stats.rewards = []

        return cfg

    def _resolve_original_cfg(self) -> DictConfig:
        """
        Create a new resolved environment configuration from the template.

        This method:
        1. Creates a deep copy of the original configuration
        2. Resolves all variable interpolations, references, and custom resolvers
        - Any randomness in resolvers (e.g. ${sampling:0, 100, 50}) will be
            evaluated at this point, potentially resulting in a different environment
            each time this method is called

        Returns:
            The resolved configuration object with all references replaced by concrete values
        """
        cfg = OmegaConf.create(copy.deepcopy(self._original_cfg))

        # Insert stats into the configuration
        cfg = self._insert_stats_into_cfg(cfg)

        OmegaConf.resolve(cfg)
        return cfg

    def initialize_episode(self):
        """Initialize a new episode."""
        # Instantiate map builder
        self._map_builder = hydra.utils.instantiate(
            self.active_cfg.game.map_builder,
            _recursive_=self.active_cfg.game.recursive_map_builder,
        )

        # Build map and verify agent count
        env_map = self._map_builder.build()
        map_agents = np.count_nonzero(np.char.startswith(env_map, "agent"))
        if self.active_cfg.game.num_agents != map_agents:
            raise ValueError(
                f"Number of agents {self.active_cfg.game.num_agents} "
                f"does not match number of agents in map {map_agents}"
            )

        # Create C++ environment
        self._c_env = MettaGrid(self.active_cfg, env_map)
        self._grid_env = self._c_env
        self._num_agents = self._c_env.num_agents()
        self._env = self._grid_env

        # update stats for next episode
        total_steps = self._stats.get("total_steps", 0) + self._stats.get("steps", 0)
        total_rewards = self._stats.get("total_rewards", []) + self._stats.get("rewards", [])
        self._stats = {"steps": 0, "rewards": [], "total_steps": total_steps, "total_rewards": total_rewards}

    def reset(self, seed=None, options=None):
        """
        Reset the environment for a new episode.

        Args:
            seed: Random seed
            options: Additional options for resetting

        Returns:
            Tuple of (observations, info)
        """

        # Configure random seed if provided
        if seed is not None:
            np.random.seed(seed)

        # resolve a new map
        self.active_cfg = self._resolve_original_cfg()

        self.initialize_episode()
        self._c_env.set_buffers(self.observations, self.terminals, self.truncations, self.rewards)

        # Reset the environment and return initial observation
        obs, infos = self._c_env.reset()
        return obs, infos

    def step(self, actions):
        """
        Take a step in the environment.

        Args:
            actions: Array of actions for each agent

        Returns:
            Tuple of (observations, rewards, terminals, truncations, infos)
        """
        # Update stats
        self._stats["steps"] += 1
        self._stats["rewards"] = self._c_env.get_episode_rewards()

        self.actions[:] = np.array(actions).astype(np.uint32)
        self._c_env.step(self.actions)

        if self.active_cfg.normalize_rewards:
            self.rewards -= self.rewards.mean()

        # if this step completes the episode, compute the stats
        if self.done:
            self.process_episode_stats()

        return self.observations, self.rewards, self.terminals, self.truncations, self.infos

    def process_episode_stats(self):
        """
        Process statistics at the end of an episode.

        Args:
            infos: Dictionary to store information about the episode
        """
        episode_rewards = self._c_env.get_episode_rewards()
        episode_rewards_sum = episode_rewards.sum()
        episode_rewards_mean = episode_rewards_sum / self._num_agents

        self.infos.update(
            {
                "episode/reward.sum": episode_rewards_sum,
                "episode/reward.mean": episode_rewards_mean,
                "episode/reward.min": episode_rewards.min(),
                "episode/reward.max": episode_rewards.max(),
                "episode_length": self._c_env.current_timestep(),
            }
        )

        stats = self._c_env.get_episode_stats()

        self.infos["episode_rewards"] = episode_rewards
        self.infos["agent_raw"] = stats["agent"]
        self.infos["game"] = stats["game"]
        self.infos["agent"] = {}

        # Aggregate agent statistics
        for agent_stats in stats["agent"]:
            for name, value in agent_stats.items():
                self.infos["agent"][name] = self.infos["agent"].get(name, 0) + value

        # Calculate per-agent averages
        for name, value in self.infos["agent"].items():
            self.infos["agent"][name] = value / self._num_agents

    @property
    def _max_steps(self):
        """Maximum number of steps allowed in an episode."""
        return self.active_cfg.game.max_steps

    @property
    def single_observation_space(self):
        """Observation space for a single agent."""
        return self._env.observation_space

    @property
    def single_action_space(self):
        """Action space for a single agent."""
        return self._env.action_space

    def action_names(self):
        """Get names of available actions."""
        return self._env.action_names()

    @property
    def player_count(self):
        """Number of players/agents in the environment."""
        return self._num_agents

    @property
    def num_agents(self):
        """Number of agents in the environment."""
        return self._num_agents

    @property
    def done(self):
        return self.terminals.all() or self.truncations.all()

    @property
    def grid_features(self):
        """Features of the grid."""
        return self._env.grid_features()

    @property
    def global_features(self):
        """Global features of the environment."""
        return []

    @property
    def render_mode(self):
        """Mode for rendering the environment."""
        return self._render_mode

    @property
    def map_width(self):
        """Width of the environment map."""
        return self._c_env.map_width()

    @property
    def map_height(self):
        """Height of the environment map."""
        return self._c_env.map_height()

    @property
    def grid_objects(self):
        """Objects in the grid."""
        return self._c_env.grid_objects()

    @property
    def max_action_args(self):
        """Maximum number of arguments for actions."""
        return self._c_env.max_action_args()

    @property
    def action_success(self):
        """Success status of the most recent actions."""
        return np.asarray(self._c_env.action_success())

    def object_type_names(self):
        """Names of object types in the environment."""
        return self._c_env.object_type_names()

    def close(self):
        """Close the environment."""
        pass


class MettaGridEnvSet(MettaGridEnv):
    """
    A wrapper around MettaGridEnv that allows for multiple configurations to be used for training.

    This class overrides the base method "_resolve_original_cfg" to choose from a list of options.

    ex:
        _target_: mettagrid.mettagrid_env.MettaGridEnvSet

        envs:
        - /env/mettagrid/simple
        - /env/mettagrid/bases

        probabilities:
        - 0.5
        - 0.5

    """

    def __init__(
        self,
        cfg: Union[DictConfig, ListConfig],
        weights: List[float] | None = None,
        render_mode: Optional[str] = None,
        buf=None,
        **kwargs,
    ):
        """
        Initialize a MettaGridEnvSet.

        Args:
            cfg: provided OmegaConf configuration
                - cfg.env should provide sub-configurations

            weights: weights for selecting environments.
                - Will be normalized to sum to 1.
                - If None, uniform distribution will be used.

            render_mode: Mode for rendering the environment
            buf: Buffer for Pufferlib
            **kwargs: Additional arguments passed to parent classes
        """
        self._original_cfg_paths = cfg.envs

        # Validate that all environments have the same agent count
        num_agents = self._original_cfg_paths[0].game.num_agents
        for env_path in self._original_cfg_paths:
            env_cfg = config_from_path(env_path)
            if env_cfg.game.num_agents != num_agents:
                raise ValueError(
                    "For MettaGridEnvSet, the number of agents must be the same in all environments. "
                    f"Expecting {num_agents} agents, {env_path} has {env_cfg.game.num_agents} agents"
                )

        # Handle probabilities/weights
        if weights is None:
            # Use uniform distribution if no probabilities provided
            self._probabilities = [1.0 / len(self._original_cfg_paths)] * len(self._original_cfg_paths)
        else:
            # Check that probabilities match the number of environments
            if len(weights) != len(self._original_cfg_paths):
                raise ValueError(
                    f"Number of weights ({len(weights)}) must match "
                    f"number of environments ({len(self._original_cfg_paths)})"
                )

            if any(p < 0 for p in weights):
                raise ValueError("All weights must be non-negative")

            # Normalize weights to probabilities
            total = sum(weights)
            self._probabilities = [p / total for p in weights]

        super().__init__(env_cfg, render_mode, buf, **kwargs)

        # start with a random config from the set
        self.active_cfg = self._resolve_original_cfg()

    def _resolve_original_cfg(self):
        """
        Select a random configuration based on probabilities.

        Returns:
            A resolved environment configuration

        Raises:
            ValueError: If the number of agents in the selected environment
                       doesn't match the global number of agents
        """
        selected_path = np.random.choice(self._original_cfg_paths, p=self._probabilities)
        cfg = config_from_path(selected_path)
        cfg = OmegaConf.create(cfg)

        # Insert stats into the configuration
        cfg = self._insert_stats_into_cfg(cfg)

        OmegaConf.resolve(cfg)
        return cfg


def config_from_path(config_path: str) -> DictConfig:
    """
    Load a configuration from a path.

    Args:
        config_path: Path to the configuration

    Returns:
        A DictConfig object
    """
    env_cfg = hydra.compose(config_name=config_path)

    # Remove path prefix from the config
    if config_path.startswith("/"):
        config_path = config_path[1:]
    path = config_path.split("/")
    for p in path[:-1]:
        env_cfg = env_cfg[p]
    return env_cfg


# Ensure resolvers are registered when this module is imported
register_resolvers()
