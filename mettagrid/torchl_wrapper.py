import logging

import torch
from tensordict import TensorDict
from torchrl.data import (
    Bounded,
    MultiCategorical,
    Stacked,
    Composite,
    StackedComposite,
)
from torchrl.envs import EnvBase

from mettagrid.mettagrid_env import MettaGridEnv

logger = logging.getLogger(__name__)

class MettaGridEnvWrapper(EnvBase):
    def __init__(self, cfg, render_mode="rgb_array"):
        super().__init__()
        self.env = MettaGridEnv(cfg, render_mode=render_mode)

        single_action_spec = MultiCategorical(nvec=(
            len(self.env._env.action_names()),
            len(self.env._env.max_action_args()) + 1,
        ))
        self.action_spec = Stacked(*([single_action_spec] * self.env._num_agents), dim=0)

        single_observation_spec = Composite(
            grid=Bounded(
                low=0,
                high=255,
                shape=self.env.single_observation_space.shape,
                dtype=torch.uint8,
            ),
        )
        self.observation_spec = StackedComposite(
            *([single_observation_spec] *self.env._num_agents), dim=0)


    def _reset(self, tensordict=None, **kwargs):
        if tensordict is None:
            tensordict = TensorDict({}, batch_size=[self.env._num_agents])
        obs, info = self.env.reset(**kwargs)
        obs, terms, truncs, rewards = self.env._env.get_buffers()

        tensordict.update({
            "observation": torch.as_tensor(obs),
            "info": info,
        })

        return tensordict

    def _step(self, tensordict):
        action = tensordict.get("action")
        obs, reward, done, truncated, info = self.env.step(action.numpy())

        # Convert numpy arrays to tensors
        if isinstance(obs, dict):
            for k, v in obs.items():
                tensordict.set(k, torch.as_tensor(v, device=torch.device("cpu")))
        else:
            tensordict.set("observation", torch.as_tensor(obs, device=torch.device("cpu")))

        tensordict.set("done", torch.as_tensor(done, device=torch.device("cpu")))
        tensordict.set("truncated", torch.as_tensor(truncated, device=torch.device("cpu")))
        tensordict.set("reward", torch.as_tensor(reward, device=torch.device("cpu")))
        tensordict.set("info", info)
        return tensordict

    def _set_seed(self, seed):
        # self.env.seed(seed)
        pass

    def set_state(self, state):
        self.env.set_state(state)

    def forward(self, tensordict):
        return self._step(tensordict)
