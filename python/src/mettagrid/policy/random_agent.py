"""Random policy implementation for CoGames."""

import random
from collections.abc import Sequence
from typing import Any

from mettagrid.config.action_config import CHANGE_VIBE_PREFIX
from mettagrid.policy.policy import AgentPolicy, MultiAgentPolicy
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.simulator import Action, AgentObservation


def _as_action_name_list(value: Any) -> list[str]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [str(name) for name in value]
    return []


class RandomAgentPolicy(AgentPolicy):
    """Per-agent random policy with category-balanced sampling."""

    def __init__(self, policy_env_info: PolicyEnvInterface, vibe_action_p: float = 0.5):
        super().__init__(policy_env_info)
        action_names = [str(action_name) for action_name in policy_env_info.action_names]

        non_vibe_action_names = _as_action_name_list(getattr(policy_env_info, "non_vibe_action_names", None))
        if not non_vibe_action_names:
            non_vibe_action_names = [name for name in action_names if not name.startswith(CHANGE_VIBE_PREFIX)]

        vibe_action_names = _as_action_name_list(getattr(policy_env_info, "vibe_action_names", None))
        if not vibe_action_names:
            vibe_action_names = [name for name in action_names if name.startswith(CHANGE_VIBE_PREFIX)]

        self._vibe_actions = vibe_action_names
        self._non_vibe_actions = non_vibe_action_names
        self._vibe_action_p = vibe_action_p

    def step(self, obs: AgentObservation) -> Action:
        # Build list of (category, weight) for non-empty categories
        categories = []
        weights = []
        if self._vibe_actions:
            categories.append(self._vibe_actions)
            weights.append(self._vibe_action_p)
        if self._non_vibe_actions:
            categories.append(self._non_vibe_actions)
            weights.append(1.0 - self._vibe_action_p)

        chosen_category = random.choices(categories, weights=weights)[0]
        return Action(name=random.choice(chosen_category))

    def reset(self) -> None:
        """Random policy keeps no state."""
        pass


class RandomMultiAgentPolicy(MultiAgentPolicy):
    """Random multi-agent policy that samples actions uniformly from the action space."""

    short_names = ["random"]

    def __init__(self, policy_env_info: PolicyEnvInterface, device: str = "cpu", **kwargs):
        super().__init__(policy_env_info, device=device)
        self._vibe_action_p = float(kwargs.get("vibe_action_p", 0.5))

    def agent_policy(self, agent_id: int) -> AgentPolicy:
        return RandomAgentPolicy(self._policy_env_info, self._vibe_action_p)

    def agent_policies(self, num_agents: int) -> list[AgentPolicy]:
        """Get a list of AgentPolicy instances for all agents."""
        return [self.agent_policy(i) for i in range(num_agents)]
