"""
MettaGrid Environment implementation for Pufferlib.
This module provides environment classes for Metta Grid simulations.
"""

import copy
import time
import uuid
from typing import Any, Dict, List, Optional, Union

import gymnasium as gym
import hydra
import numpy as np
import pufferlib
from omegaconf import DictConfig, ListConfig, OmegaConf

from metta.util.logging import rich_logger

# Import with explicit comment about the pylint disable
from mettagrid.mettagrid_c import MettaGrid  # C extension module

logger = rich_logger(__name__)


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

        self.instance_id = str(uuid.uuid4())
        self.last_episode_info: Dict[str, Any] = {}
        self.start_time = None

        self._render_mode = render_mode
        self._original_cfg = cfg
        self.active_cfg = self._resolve_original_cfg()

        self.initialize_episode()
        super().__init__(buf)

    def _insert_progress_into_cfg(self, cfg: Union[DictConfig, ListConfig]) -> Union[DictConfig, ListConfig]:
        """
        Insert values from last_episode_info into the configuration used to resolve the environment.

        Args:
            cfg: The configuration to update
        Returns:
            The updated configuration with stats inserted
        """

        # Create cfg with stats data
        progress_cfg = OmegaConf.create({})
        progress_cfg.progress = OmegaConf.create({})

        episode_count = self.last_episode_info.get("episode/count", 0)
        progress_cfg.progress.episode_count = int(episode_count)  # Ensure int type

        mean_reward = self.last_episode_info.get("episode/reward.mean", 0.0)
        progress_cfg.progress.mean_reward = float(mean_reward)  # Convert to Python float

        filtered_mean_reward = self.last_episode_info.get("episode/reward.filtered_mean", 0.0)
        progress_cfg.progress.filtered_mean_reward = float(filtered_mean_reward)  # Convert to Python float

        last_difficulty = self.last_episode_info.get("game/difficulty", 0.0)
        progress_cfg.progress.last_difficulty = float(last_difficulty)  # Convert to Python float

        # Set struct flag to False to allow accessing undefined fields
        OmegaConf.set_struct(cfg, False)
        cfg = OmegaConf.merge(cfg, progress_cfg)
        OmegaConf.set_struct(cfg, True)

        return cfg

    def _resolve_original_cfg(self) -> Union[DictConfig, ListConfig]:
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
        cfg = self._insert_progress_into_cfg(cfg)
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

    def finalize_episode(self):
        """
        Process statistics and update progress tracking at the end of each episode.
        """

        rewards = self._c_env.get_episode_rewards()
        stats = self._c_env.get_episode_stats()
        rewards_sum = rewards.sum()
        rewards_mean = rewards_sum / self._num_agents

        # iir filter rewards mean
        filter_constant = 0.1  # ~10 episode moving average
        filtered_rewards_mean = self.last_episode_info.get("episode/reward.filtered_mean", 0.0)
        filtered_rewards_mean = filter_constant * rewards_mean + (1 - filter_constant) * filtered_rewards_mean

        # calculate the average performance for all agent stats (counters)
        agent_stats = {}
        for agent_entry in stats["agent"]:
            for name, count in agent_entry.items():
                agent_stats[name] = agent_stats.get(name, 0) + count
        for name, cumulative_count in agent_stats.items():
            agent_stats[name] = cumulative_count / self._num_agents

        # Get current timestamp and calculate duration
        current_time = time.time()
        episode_duration = current_time - self.start_time if self.start_time is not None else 0.0

        # Update everything in one operation
        episode_count = self.last_episode_info.get("episode/count", 0)

        self.last_episode_info.update(
            {
                "episode/reward.sum": rewards_sum,
                "episode/reward.mean": rewards_mean,
                "episode/reward.min": rewards.min(),
                "episode/reward.max": rewards.max(),
                "episode/totals_steps": self._c_env.current_timestep(),
                "episode/duration_sec": episode_duration,
                "episode/timestamp": current_time,
                "episode/reward.filtered_mean": filtered_rewards_mean,
                "episode/count": episode_count + 1,  # increment episode!
                "game": stats["game"],
                "game/difficulty": self.active_cfg.game.difficulty,
                "game/min_size": self.active_cfg.game.min_size,
                "game/max_size": self.active_cfg.game.max_size,
                "game/width": self.active_cfg.game.map_builder["width"],
                "game/height": self.active_cfg.game.map_builder["height"],
                # log cfg progress
                "progress/episode_count": self.active_cfg.progress.episode_count,
                "progress/mean_reward": self.active_cfg.progress.mean_reward,
                "progress/filtered_mean_reward": self.active_cfg.progress.filtered_mean_reward,
                "progress/last_difficulty": self.active_cfg.progress.last_difficulty,
                "agent": agent_stats,
            }
        )

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

        if self.active_cfg.progress.episode_count and self.active_cfg.progress.episode_count % 100 == 0:
            logger.debug(
                f"[{self.instance_id}] - resolved cfg: "
                f"episode_count = {self.active_cfg.progress.episode_count}, "
                f"episode_count/10 = {self.active_cfg.game.scaled_count}, "
                f"mean_reward = {self.active_cfg.progress.mean_reward} "
                f"game.max_size = {self.active_cfg.game.max_size} "
                f"game.size = {self.active_cfg.game.size}"
            )

        self.initialize_episode()
        self._c_env.set_buffers(self.observations, self.terminals, self.truncations, self.rewards)

        # Reset the environment and return initial (observations, infos)
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
        # Validate actions
        if not isinstance(actions, (list, np.ndarray)):
            raise TypeError(f"Actions must be a list or numpy array, got {type(actions)}")

        if len(actions) != self._num_agents:
            raise ValueError(f"Expected {self._num_agents} actions, got {len(actions)}")

        # Execute step in environment
        self.actions[:] = np.array(actions).astype(np.uint32)
        self._c_env.step(self.actions)

        if self.active_cfg.normalize_rewards:
            self.rewards -= self.rewards.mean()

        # if this step completes the episode, compute the stats
        if self.done:
            self.finalize_episode()

        return self.observations, self.rewards, self.terminals, self.truncations, self.last_episode_info

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
        first_env_cfg = config_from_path(self._original_cfg_paths[0])
        num_agents = first_env_cfg.game.num_agents

        # Improve error message with specific environment information
        for env_path in self._original_cfg_paths:
            env_cfg = config_from_path(env_path)
            if env_cfg.game.num_agents != num_agents:
                raise ValueError(
                    "For MettaGridEnvSet, the number of agents must be the same in all environments. "
                    f"Environment '{env_path}' has {env_cfg.game.num_agents} agents, but expected {num_agents} "
                    f"(from first environment '{self._original_cfg_paths[0]}')"
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
            if total == 0:
                raise ValueError("Sum of weights cannot be zero")
            self._probabilities = [p / total for p in weights]

        super().__init__(cfg, render_mode, buf, **kwargs)

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
        cfg = self._insert_progress_into_cfg(cfg)

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

    # Remove path prefix from the configuration
    if config_path.startswith("/"):
        config_path = config_path[1:]
    path = config_path.split("/")
    for p in path[:-1]:
        env_cfg = env_cfg[p]
    return env_cfg
