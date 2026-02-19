"""Random policy implementation for CoGames."""

import random

from mettagrid.policy.policy import AgentPolicy, MultiAgentPolicy
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.simulator import Action, AgentObservation


class RandomAgentPolicy(AgentPolicy):
    """Per-agent random policy with category-balanced sampling."""

    def __init__(self, policy_env_info: PolicyEnvInterface, vibe_action_p: float = 0.5):
        super().__init__(policy_env_info)
        if not 0.0 <= vibe_action_p <= 1.0:
            raise ValueError(f"vibe_action_p must be in [0.0, 1.0], got {vibe_action_p}")

        self._vibe_actions = list(policy_env_info.vibe_action_names)
        self._primary_actions = list(policy_env_info.action_names)
        if not self._vibe_actions and not self._primary_actions:
            raise ValueError("PolicyEnvInterface must define at least one action")
        self._vibe_action_p = float(vibe_action_p)

    def step(self, obs: AgentObservation) -> Action:
        # Build list of (category, weight) for non-empty categories.
        categories = []
        weights = []
        if self._vibe_actions:
            categories.append(self._vibe_actions)
            weights.append(self._vibe_action_p)
        if self._primary_actions:
            categories.append(self._primary_actions)
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
        vibe_action_p = float(kwargs.get("vibe_action_p", 0.5))
        if not 0.0 <= vibe_action_p <= 1.0:
            raise ValueError(f"vibe_action_p must be in [0.0, 1.0], got {vibe_action_p}")
        self._vibe_action_p = vibe_action_p

    def agent_policy(self, agent_id: int) -> AgentPolicy:
        return RandomAgentPolicy(self._policy_env_info, self._vibe_action_p)

    def agent_policies(self, num_agents: int) -> list[AgentPolicy]:
        """Get a list of AgentPolicy instances for all agents."""
        return [self.agent_policy(i) for i in range(num_agents)]
