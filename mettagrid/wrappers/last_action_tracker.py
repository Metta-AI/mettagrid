from functools import lru_cache
import re
import gymnasium as gym
import numpy as np

class LastActionTracker(gym.Wrapper):
    def __init__(self, env):
        print("Init LastActionTracker")
        super(LastActionTracker, self).__init__(env)
        self._last_actions = None

    def reset(self, **kwargs):
        self._last_actions = np.zeros((self.unwrapped.player_count, 2), dtype=np.int32)
        obs, infos = self.env.reset(**kwargs)
        return self._augment_observations(obs), infos

    def step(self, actions):
        print("LastActionTracker.step")
        obs, rewards, terms, truncs, infos = self.env.step(actions)
        self._last_actions = actions

        return self._augment_observations(obs), rewards, terms, truncs, infos

    def _augment_observations(self, obs):
        print("LastActionTracker._augment_observations")
        print("Obs: ", obs)
        return [{
            "last_action": self._last_actions[agent],
            **agent_obs
        } for agent, agent_obs in enumerate(obs)]
        num_agents, num_features, h, w = obs.shape
        print("num_agents:", num_agents)
        print("num_features:", num_features)
        print("h:", h)
        print("w:", w)

        # for agent_id in range(num_agents):
        #     last_action_feature = np.zeros((h, w), dtype=obs.dtype)
        #     last_action_feature[h // 2, w // 2] = self._last_actions[agent_id][0]
        #     # Insert last_action_feature at num_agents, after num_features:
        #     obs = np.concatenate((obs, last_action_feature[None, :, :]), axis=1)

        return obs

    @property
    def observation_space(self):
        print("LastActionTracker.observation_space")
        return gym.spaces.Dict({
            "last_action": gym.spaces.Box(
                low=0, high=255, shape=(2,), dtype=np.int32
            ),
            **self.env.observation_space.spaces
        })
