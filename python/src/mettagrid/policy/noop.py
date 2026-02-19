"""Noop policy implementation."""

import numpy as np

from mettagrid.config.action_config import CHANGE_VIBE_PREFIX
from mettagrid.mettagrid_c import dtype_actions
from mettagrid.policy.policy import AgentPolicy, MultiAgentPolicy
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.simulator import Action, AgentObservation


class NoopAgentPolicy(AgentPolicy):
    """Per-agent noop policy."""

    def __init__(self, policy_env_info: PolicyEnvInterface):
        super().__init__(policy_env_info)
        non_vibe_action_names = (
            policy_env_info.non_vibe_action_names
            if policy_env_info.non_vibe_action_names
            else [name for name in policy_env_info.action_names if not name.startswith(CHANGE_VIBE_PREFIX)]
        )
        self._noop_index = non_vibe_action_names.index("noop")

    def step(self, obs: AgentObservation) -> Action:
        """Return the noop action for the agent."""
        return Action(name="noop")


class NoopPolicy(MultiAgentPolicy):
    """Policy that always selects the noop action when available."""

    short_names = ["noop"]

    def __init__(self, policy_env_info: PolicyEnvInterface, device: str = "cpu"):
        super().__init__(policy_env_info, device=device)
        non_vibe_action_names = (
            policy_env_info.non_vibe_action_names
            if policy_env_info.non_vibe_action_names
            else [name for name in policy_env_info.action_names if not name.startswith(CHANGE_VIBE_PREFIX)]
        )
        self._noop_action_value = dtype_actions.type(non_vibe_action_names.index("noop"))

    def agent_policy(self, agent_id: int) -> AgentPolicy:
        """Get an AgentPolicy instance configured with the noop action id."""
        return NoopAgentPolicy(self._policy_env_info)

    def step_batch(self, raw_observations: np.ndarray, raw_actions: np.ndarray) -> None:
        raw_actions[...] = self._noop_action_value
