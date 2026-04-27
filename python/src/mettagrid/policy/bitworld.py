"""BitWorld smoke-test policies."""

from __future__ import annotations

import numpy as np

from mettagrid.bitworld import BITWORLD_ACTION_COUNT, bitworld_action_name, dpad_action_indices
from mettagrid.policy.policy import AgentPolicy, MultiAgentPolicy
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.simulator import Action, AgentObservation


class _BitWorldActionAgentPolicy(AgentPolicy):
    def __init__(self, policy_env_info: PolicyEnvInterface, parent: "_BitWorldActionPolicy"):
        super().__init__(policy_env_info)
        self._parent = parent

    def step(self, obs: AgentObservation) -> Action:
        del obs
        return Action(name=bitworld_action_name(self._parent.next_action()))


class _BitWorldActionPolicy(MultiAgentPolicy):
    def __init__(self, policy_env_info: PolicyEnvInterface, device: str = "cpu", *, seed: int = 0):
        super().__init__(policy_env_info, device=device)
        if len(policy_env_info.action_names) != BITWORLD_ACTION_COUNT:
            raise ValueError(
                f"BitWorld policies require {BITWORLD_ACTION_COUNT} action names, "
                f"got {len(policy_env_info.action_names)}"
            )
        self._rng = np.random.default_rng(seed)

    def agent_policy(self, agent_id: int) -> AgentPolicy:
        del agent_id
        return _BitWorldActionAgentPolicy(self._policy_env_info, self)

    def step_batch(self, raw_observations: np.ndarray, raw_actions: np.ndarray) -> None:
        del raw_observations
        raw_actions[...] = self.next_actions(raw_actions.shape)

    def next_action(self) -> int:
        return int(np.asarray(self.next_actions(())).item())

    def next_actions(self, shape: tuple[int, ...]) -> np.ndarray:
        raise NotImplementedError


class BitWorldRandomActionPolicy(_BitWorldActionPolicy):
    """Uniformly sample the BitWorld trainable action-index space."""

    short_names = ["bitworld_random_action"]

    def __init__(
        self,
        policy_env_info: PolicyEnvInterface,
        device: str = "cpu",
        *,
        seed: int = 0,
        include_noop: bool = True,
    ):
        super().__init__(policy_env_info, device=device, seed=seed)
        self._low = 0 if include_noop else 1

    def next_actions(self, shape: tuple[int, ...]) -> np.ndarray:
        return self._rng.integers(self._low, BITWORLD_ACTION_COUNT, size=shape, dtype=np.int32)


class BitWorldRandomDpadPolicy(_BitWorldActionPolicy):
    """Uniformly sample noop/up/down/left/right action indices."""

    short_names = ["bitworld_random_dpad"]

    def __init__(
        self,
        policy_env_info: PolicyEnvInterface,
        device: str = "cpu",
        *,
        seed: int = 0,
        include_noop: bool = True,
    ):
        super().__init__(policy_env_info, device=device, seed=seed)
        self._actions = dpad_action_indices(include_noop=include_noop)

    def next_actions(self, shape: tuple[int, ...]) -> np.ndarray:
        indices = self._rng.integers(0, len(self._actions), size=shape)
        return self._actions[indices]


__all__ = [
    "BitWorldRandomActionPolicy",
    "BitWorldRandomDpadPolicy",
]
