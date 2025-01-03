import gymnasium as gym
from gymnasium.spaces import Box
import numpy as np

class LastActionTracker(gym.Wrapper):
    """
    Wrap an environment and add last_action and last_action_argument as new
    features for each agent. This might help the agents to keep track of what
    they are doing and might help them not get stuck in back and forth loops.
    """
    def __init__(self, env):
        super(LastActionTracker, self).__init__(env)
        self._env = env
        self._last_actions = np.zeros((self.num_agents(), 2), dtype=np.uint8)

    def reset(self, **kwargs):
        self._last_actions = np.zeros((self.num_agents(), 2), dtype=np.uint8)
        obs, infos = self.env.reset(**kwargs)
        return self._augment_observations(obs), infos

    def step(self, actions):
        obs, rewards, terms, truncs, infos = self._env.step(actions)
        # Keep track of the last actions:
        self._last_actions = actions
        return self._augment_observations(obs), rewards, terms, truncs, infos
        #return obs, rewards, terms, truncs, infos

    def _augment_observations(self, obs):
        """
        Add last_action and last_action_argument as new features for each agent.
        """
        shape = obs.shape
        last_action_feature = np.zeros(
            (shape[0], 2, shape[2], shape[3]),
            dtype=obs.dtype
        )
        #Set the middle of the last action features to the last action and
        #last action argument:
        for agentId in range(shape[0]):
            last_action_feature[
                agentId, :, shape[2]//2, shape[3]//2
            ] = self._last_actions[agentId]

        #
        obs = np.concatenate((obs, last_action_feature), axis=1)

        return obs

    def grid_features(self):
        """
        Add last_action and last_action_argument names.
        """
        return self._env.grid_features() + [
            "last_action", "last_action_argument"
        ]

    @property
    def observation_space(self):
        box = self._env.observation_space
        return Box(
            0,
            255,
            (box.shape[0] + 2, box.shape[1], box.shape[2]),
            np.uint8
        )
