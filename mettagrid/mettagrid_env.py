import copy
from typing import Any, Dict, List

import gymnasium as gym
import hydra
import numpy as np
import pufferlib
from omegaconf import DictConfig, OmegaConf

from mettagrid.mettagrid_c import MettaGrid  # pylint: disable=E0611
from mettagrid.resolvers import register_resolvers


class MettaGridEnv(pufferlib.PufferEnv, gym.Env):
    def __init__(self, env_config: DictConfig, render_mode: str, buf=None, **kwargs):
        self._render_mode = render_mode
        self._original_env_config = env_config

        # Initialize episode_stats in the original config if it doesn't exist
        if "episode_stats" not in self._original_env_config:
            self._original_env_config.episode_stats = OmegaConf.create({})

        self._episode_env_config = self._get_new_env_config()
        self._reset_env()
        self.should_reset = False
        self._renderer = None

        super().__init__(buf)

    def _get_new_env_config(self):
        """Create a fresh copy of the environment config for this episode."""
        episode_config = OmegaConf.create(copy.deepcopy(self._original_env_config))
        OmegaConf.resolve(episode_config)
        return episode_config

    def _reset_env(self):
        self._map_builder = hydra.utils.instantiate(self._episode_env_config.game.map_builder)
        env_map = self._map_builder.build()
        map_agents = np.count_nonzero(np.char.startswith(env_map, "agent"))
        assert self._episode_env_config.game.num_agents == map_agents, (
            f"Number of agents {self._episode_env_config.game.num_agents} does not match number of agents in map {map_agents}"
        )

        self._c_env = MettaGrid(self._env_cfg, env_map)
        self._grid_env = self._c_env
        self._num_agents = self._c_env.num_agents()

        env = self._grid_env

        self._env = env
        # self._env = RewardTracker(self._env)
        # self._env = FeatureMasker(self._env, self._cfg.hidden_features)

    def reset(self, seed=None, options=None):
        self._episode_env_config = self._get_new_env_config()
        self._reset_env()

        self._c_env.set_buffers(self.observations, self.terminals, self.truncations, self.rewards)

        # obs, infos = self._env.reset(**kwargs)
        # return obs, infos
        obs, infos = self._c_env.reset()
        self.should_reset = False
        return obs, infos

    def step(self, actions):
        self.actions[:] = np.array(actions).astype(np.uint32)
        self._c_env.step(self.actions)

        if self._episode_env_config.normalize_rewards:
            self.rewards -= self.rewards.mean()

        infos = {}
        if self.terminals.all() or self.truncations.all():
            self.process_episode_stats(infos)
            # Note: should_reset is now set in process_episode_stats

        return self.observations, self.rewards, self.terminals, self.truncations, infos

    def process_episode_stats(self, infos: Dict[str, Any]):
        """Process episode statistics and update configs with collected data.

        This method serves as the main entry point for handling episode statistics.
        It collects the statistics and then updates the relevant configurations.

        Args:
            infos: Dictionary to be populated with episode information
        """
        # First collect all the stats
        collected_stats = self.collect_episode_stats()

        # Update the infos dictionary with the collected stats
        for key, value in collected_stats["episode"].items():
            infos[f"episode/{key}"] = value

        infos["episode_rewards"] = collected_stats["episode_rewards"]
        infos["agent_raw"] = collected_stats["agent_raw"]
        infos["game"] = collected_stats["game"]
        infos["agent"] = collected_stats["agent_avg"]

        # Update the configs with the collected stats
        self.update_config_with_stats(collected_stats)

        # Mark that we should reset after processing stats
        self.should_reset = True

    def collect_episode_stats(self) -> Dict[str, Any]:
        """Collect all episode statistics into a structured dictionary.

        Returns:
            A dictionary containing all episode statistics organized by category
        """
        # Get episode rewards
        episode_rewards = self._c_env.get_episode_rewards()
        episode_rewards_sum = episode_rewards.sum()
        episode_rewards_mean = episode_rewards_sum / self._num_agents

        # Get episode stats from the environment
        stats = self._c_env.get_episode_stats()

        # Create the main episode metrics
        episode_stats = {
            "reward.sum": float(episode_rewards_sum),
            "reward.mean": float(episode_rewards_mean),
            "reward.min": float(episode_rewards.min()),
            "reward.max": float(episode_rewards.max()),
            "episode_length": int(self._c_env.current_timestep()),
        }

        # Calculate per-agent averages
        agent_avg = {}
        for agent_stats in stats["agent"]:
            for n, v in agent_stats.items():
                agent_avg[n] = agent_avg.get(n, 0) + v

        for n, v in agent_avg.items():
            agent_avg[n] = v / self._num_agents

        # Compile all stats into a single structured dictionary
        return {
            "episode": episode_stats,
            "episode_rewards": episode_rewards,
            "agent_raw": stats["agent"],
            "agent_avg": agent_avg,
            "game": stats["game"],
        }

    def update_config_with_stats(self, stats: Dict[str, Any]):
        """Update the configuration objects with the collected statistics.

        Args:
            stats: Dictionary containing the collected statistics
        """
        # Ensure episode_stats exists in the original config
        if "episode_stats" not in self._original_env_config:
            self._original_env_config.episode_stats = OmegaConf.create({})

        # Update main episode stats
        for key, value in stats["episode"].items():
            self._original_env_config.episode_stats[key] = value

        # Update agent stats
        if "agent" not in self._original_env_config.episode_stats:
            self._original_env_config.episode_stats.agent = OmegaConf.create({})
        for n, v in stats["agent_avg"].items():
            self._original_env_config.episode_stats.agent[n] = float(v)

        # Update game stats
        if "game" not in self._original_env_config.episode_stats:
            self._original_env_config.episode_stats.game = OmegaConf.create({})
        for key, value in stats["game"].items():
            self._original_env_config.episode_stats.game[key] = (
                float(value) if isinstance(value, (int, float, np.number)) else value
            )

        # Update episode_env_config with the latest stats
        if "episode_stats" not in self._episode_env_config:
            self._episode_env_config.episode_stats = OmegaConf.create({})

        for key, value in OmegaConf.to_container(self._original_env_config.episode_stats):
            OmegaConf.update(self._episode_env_config.episode_stats, key, value, merge=True)

    @property
    def _max_steps(self):
        return self._episode_env_config.game.max_steps

    @property
    def single_observation_space(self):
        return self._env.observation_space

    @property
    def single_action_space(self):
        return self._env.action_space

    def action_names(self):
        return self._env.action_names()

    @property
    def player_count(self):
        return self._num_agents

    @property
    def num_agents(self):
        return self._num_agents

    def render(self):
        if self._renderer is None:
            return None

        return self._renderer.render(self._c_env.current_timestep(), self._c_env.grid_objects())

    @property
    def done(self):
        return self.should_reset

    @property
    def grid_features(self):
        return self._env.grid_features()

    @property
    def global_features(self):
        return []

    @property
    def render_mode(self):
        return self._render_mode

    @property
    def map_width(self):
        return self._c_env.map_width()

    @property
    def map_height(self):
        return self._c_env.map_height()

    @property
    def grid_objects(self):
        return self._c_env.grid_objects()

    @property
    def max_action_args(self):
        return self._c_env.max_action_args()

    @property
    def action_success(self):
        return np.asarray(self._c_env.action_success())

    def object_type_names(self):
        return self._c_env.object_type_names()

    def get_episode_stats(self):
        """
        Return the current episode stats stored in the config
        """
        return (
            OmegaConf.to_container(self._original_env_config.episode_stats)
            if hasattr(self._original_env_config, "episode_stats")
            else {}
        )

    def close(self):
        pass


class MettaGridEnvSet(MettaGridEnv):
    """
    This is a wrapper around MettaGridEnv that allows for multiple environments to be used for training.
    """

    def __init__(self, env_config: DictConfig, probabilities: List[float] | None, render_mode: str, buf=None, **kwargs):
        self._env_configs = env_config.envs
        self._num_agents_global = env_config.num_agents
        self._probabilities = probabilities
        self._episode_env_config = self._get_new_env_config()

        super().__init__(env_config, render_mode, buf, **kwargs)
        self._original_env_config = None  # we don't use this with multiple envs, so we clear it to emphasize that fact

    def _get_new_env_config(self):
        selected_env = np.random.choice(self._env_configs, p=self._probabilities)
        env_config = config_from_path(selected_env)
        if self._num_agents_global != env_config.game.num_agents:
            raise ValueError(
                "For MettaGridEnvSet, the number of agents must be the same for all environments. "
                f"Global: {self._num_agents_global}, Env: {env_config.game.num_agents}"
            )

        env_config = OmegaConf.create(env_config)
        OmegaConf.resolve(env_config)
        return env_config


def make_env_from_config(config_path: str, *args, **kwargs):
    config = OmegaConf.load(config_path)
    env = MettaGridEnv(config, *args, **kwargs)
    return env


def config_from_path(config_path: str) -> DictConfig:
    env_config = hydra.compose(config_name=config_path)

    # when hydra loads a config, it "prefixes" the keys with the path of the config file.
    # We don't want that prefix, so we remove it.
    if config_path.startswith("/"):
        config_path = config_path[1:]
    path = config_path.split("/")
    for p in path[:-1]:
        env_config = env_config[p]
    return env_config


# Ensure resolvers are registered when this module is imported
register_resolvers()
