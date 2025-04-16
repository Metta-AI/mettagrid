"""
MettaGrid Environment implementation for Pufferlib.
This module provides environment classes for Metta Grid simulations.
"""

import copy
from typing import Any, Dict, List, Optional

import gymnasium as gym
import hydra
import numpy as np
import pufferlib
from omegaconf import DictConfig, OmegaConf

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

    def __init__(self, env_cfg: DictConfig, render_mode: Optional[str], buf=None, **kwargs):
        """
        Initialize a MettaGridEnv.

        Args:
            env_cfg: Configuration for the environment
            render_mode: Mode for rendering the environment
            buf: Buffer for Pufferlib
            **kwargs: Additional arguments passed to parent classes
        """
        self._render_mode = render_mode
        self._cfg_template = env_cfg
        self._env_cfg = self._get_new_env_cfg()
        self._reset_env()
        self.should_reset = False
        self._renderer = None

        super().__init__(buf)

    def _get_new_env_cfg(self):
        """Create a new resolved environment configuration from the template."""
        env_cfg = OmegaConf.create(copy.deepcopy(self._cfg_template))
        OmegaConf.resolve(env_cfg)
        return env_cfg

    def _reset_env(self):
        """Reset the internal environment state with a new configuration."""
        # Instantiate map builder
        self._map_builder = hydra.utils.instantiate(
            self._env_cfg.game.map_builder,
            _recursive_=self._env_cfg.game.recursive_map_builder,
        )

        # Build map and verify agent count
        env_map = self._map_builder.build()
        map_agents = np.count_nonzero(np.char.startswith(env_map, "agent"))
        if self._env_cfg.game.num_agents != map_agents:
            raise ValueError(
                f"Number of agents {self._env_cfg.game.num_agents} does not match number of agents in map {map_agents}"
            )

        # Create C++ environment
        self._c_env = MettaGrid(self._env_cfg, env_map)
        self._grid_env = self._c_env
        self._num_agents = self._c_env.num_agents()
        self._env = self._grid_env

        # Commented out code preserved for reference
        # self._env = RewardTracker(self._env)
        # self._env = FeatureMasker(self._env, self._cfg.hidden_features)

    def reset(self, seed=None, options=None):
        """
        Reset the environment.

        Args:
            seed: Random seed
            options: Additional options for resetting

        Returns:
            Tuple of (observations, info)
        """
        self._env_cfg = self._get_new_env_cfg()
        self._reset_env()

        self._c_env.set_buffers(self.observations, self.terminals, self.truncations, self.rewards)

        # Commented out code preserved for reference
        # obs, infos = self._env.reset(**kwargs)
        # return obs, infos

        obs, infos = self._c_env.reset()
        self.should_reset = False
        return obs, infos

    def step(self, actions):
        """
        Take a step in the environment.

        Args:
            actions: Array of actions for each agent

        Returns:
            Tuple of (observations, rewards, terminals, truncations, infos)
        """
        self.actions[:] = np.array(actions).astype(np.uint32)
        self._c_env.step(self.actions)

        if self._env_cfg.normalize_rewards:
            self.rewards -= self.rewards.mean()

        infos = {}
        if self.terminals.all() or self.truncations.all():
            self.process_episode_stats(infos)
            self.should_reset = True

        return self.observations, self.rewards, self.terminals, self.truncations, infos

    def process_episode_stats(self, infos: Dict[str, Any]):
        """
        Process statistics at the end of an episode.

        Args:
            infos: Dictionary to store information about the episode
        """
        episode_rewards = self._c_env.get_episode_rewards()
        episode_rewards_sum = episode_rewards.sum()
        episode_rewards_mean = episode_rewards_sum / self._num_agents

        infos.update(
            {
                "episode/reward.sum": episode_rewards_sum,
                "episode/reward.mean": episode_rewards_mean,
                "episode/reward.min": episode_rewards.min(),
                "episode/reward.max": episode_rewards.max(),
                "episode_length": self._c_env.current_timestep(),
            }
        )

        stats = self._c_env.get_episode_stats()

        infos["episode_rewards"] = episode_rewards
        infos["agent_raw"] = stats["agent"]
        infos["game"] = stats["game"]
        infos["agent"] = {}

        # Aggregate agent statistics
        for agent_stats in stats["agent"]:
            for name, value in agent_stats.items():
                infos["agent"][name] = infos["agent"].get(name, 0) + value

        # Calculate per-agent averages
        for name, value in infos["agent"].items():
            infos["agent"][name] = value / self._num_agents

    @property
    def _max_steps(self):
        """Maximum number of steps allowed in an episode."""
        return self._env_cfg.game.max_steps

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

    def render(self):
        """Render the environment if a renderer is available."""
        if self._renderer is None:
            return None

        return self._renderer.render(self._c_env.current_timestep(), self._c_env.grid_objects())

    @property
    def done(self):
        """Whether the episode is completed and needs reset."""
        return self.should_reset

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
    A wrapper around MettaGridEnv that allows for multiple environments to be used for training.

    This class randomly selects from a set of environments based on provided probabilities.
    """

    def __init__(
        self,
        env_cfg: DictConfig,
        probabilities: List[float] | None,
        render_mode: str,
        buf=None,
        **kwargs,
    ):
        """
        Initialize a MettaGridEnvSet.

        Args:
            env_cfg: Configuration containing multiple environment configs
            probabilities: Probability distribution for selecting environments
            render_mode: Mode for rendering the environment
            buf: Buffer for Pufferlib
            **kwargs: Additional arguments passed to parent classes
        """
        self._env_cfgs = env_cfg.envs
        self._num_agents_global = env_cfg.num_agents
        self._probabilities = probabilities
        self._env_cfg = self._get_new_env_cfg()

        super().__init__(env_cfg, render_mode, buf, **kwargs)
        # Clear template as it's not used with multiple environments
        self._cfg_template = None

    def _get_new_env_cfg(self):
        """
        Select a random environment configuration based on probabilities.

        Returns:
            A resolved environment configuration

        Raises:
            ValueError: If the number of agents in the selected environment
                       doesn't match the global number of agents
        """
        selected_env = np.random.choice(self._env_cfgs, p=self._probabilities)
        env_cfg = config_from_path(selected_env)

        if self._num_agents_global != env_cfg.game.num_agents:
            raise ValueError(
                "For MettaGridEnvSet, the number of agents must be the same for all environments. "
                f"Global: {self._num_agents_global}, Env: {env_cfg.game.num_agents}"
            )

        env_cfg = OmegaConf.create(env_cfg)
        OmegaConf.resolve(env_cfg)
        return env_cfg


def make_env_from_cfg(cfg_path: str, *args, **kwargs):
    """
    Create a MettaGridEnv from a configuration file.

    Args:
        cfg_path: Path to the configuration file
        *args: Additional positional arguments for MettaGridEnv
        **kwargs: Additional keyword arguments for MettaGridEnv

    Returns:
        A MettaGridEnv instance
    """
    cfg = OmegaConf.load(cfg_path)
    env = MettaGridEnv(cfg, *args, **kwargs)
    return env


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
