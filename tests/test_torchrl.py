import pytest
import torch
from torchrl.envs import EnvBase
from tensordict import TensorDict
from mettagrid.torchl_wrapper import MettaGridEnvWrapper
from mettagrid.mettagrid_env import make_env_from_cfg
import hydra
from omegaconf import OmegaConf

def get_config():
    return OmegaConf.load("configs/puffer.yaml")

def test_env_initialization():
    cfg = get_config()
    env = MettaGridEnvWrapper(cfg=cfg)
    assert isinstance(env, EnvBase)
    assert hasattr(env, 'action_spec')
    assert hasattr(env, 'observation_spec')
    assert hasattr(env, 'reward_spec')
    assert hasattr(env, 'done_spec')

def test_env_reset():
    cfg = get_config()
    env = MettaGridEnvWrapper(cfg=cfg)
    tensordict = env.reset()
    assert isinstance(tensordict, TensorDict)
    assert tensordict.get("observation") is not None
    assert tensordict.get("info") is not None

def test_env_step():
    cfg = get_config()
    env = MettaGridEnvWrapper(cfg=cfg)
    tensordict = env.reset()

    # Create a valid action tensor
    action = torch.zeros(env.action_spec.shape, dtype=torch.long)
    tensordict.set("action", action)

    next_tensordict = env.step(tensordict)
    assert isinstance(next_tensordict, TensorDict)
    assert next_tensordict.get("observation") is not None
    assert next_tensordict.get("done") is not None
    assert next_tensordict.get("reward") is not None
    assert next_tensordict.get("truncated") is not None
    assert next_tensordict.get("info") is not None

