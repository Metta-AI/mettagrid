from __future__ import annotations

import ctypes

import gymnasium as gym
import numpy as np

from mettagrid.policy.policy import AgentPolicy, NimMultiAgentPolicy
from mettagrid.policy.policy_env_interface import PolicyEnvInterface


class _RecordingNimPolicy:
    def __init__(self) -> None:
        self.agent_ids: list[int] = []

    def step_batch(
        self,
        agent_ids_ptr,
        subset_len: int,
        num_agents: int,
        _num_tokens: int,
        _token_dim: int,
        _obs_data: int,
        _action_count: int,
        action_data: int,
    ) -> None:
        self.agent_ids = [int(agent_ids_ptr[index]) for index in range(subset_len)]
        actions = np.ctypeslib.as_array(
            ctypes.cast(action_data, ctypes.POINTER(ctypes.c_int32)),
            shape=(num_agents,),
        )
        for agent_id in self.agent_ids:
            actions[agent_id] = agent_id + 10


class _NimPolicy(NimMultiAgentPolicy):
    def __init__(self, policy_env_info: PolicyEnvInterface, nim_policy: _RecordingNimPolicy):
        self.nim_policy = nim_policy
        super().__init__(policy_env_info, nim_policy_factory=lambda _env_json: nim_policy)

    def agent_policy(self, agent_id: int) -> AgentPolicy:
        raise NotImplementedError(agent_id)


def test_nim_policy_steps_slot_indexed_batch() -> None:
    nim_policy = _RecordingNimPolicy()
    policy = _NimPolicy(_policy_env_info(), nim_policy)
    observations = np.zeros((6, 3, 4), dtype=np.uint8)
    actions = np.zeros(6, dtype=np.int32)

    policy.step_batch(observations, actions)

    assert nim_policy.agent_ids == [0, 1, 2, 3, 4, 5]
    assert actions.tolist() == [10, 11, 12, 13, 14, 15]


def _policy_env_info() -> PolicyEnvInterface:
    return PolicyEnvInterface.from_spaces(
        observation_space=gym.spaces.Box(low=0, high=255, shape=(3, 4), dtype=np.uint8),
        action_space=gym.spaces.Discrete(20),
        num_agents=6,
        action_names=[str(i) for i in range(20)],
    )
