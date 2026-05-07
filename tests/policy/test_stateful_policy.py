from __future__ import annotations

import sys

import pytest

from mettagrid.policy.policy import StatefulAgentPolicy, StatefulPolicyImpl
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.simulator import Action, AgentObservation


class ScriptedStatefulPolicy(StatefulPolicyImpl[int]):
    def initial_agent_state(self) -> int:
        return 0

    def step_with_state(self, obs: AgentObservation, state: int) -> tuple[Action, int]:
        return Action("noop"), state + 1


def test_stateful_agent_policy_does_not_require_torch_for_scripted_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, "torch", raising=False)
    policy = StatefulAgentPolicy(
        ScriptedStatefulPolicy(),
        PolicyEnvInterface(
            obs_features=[],
            tags=[],
            action_names=["noop"],
            num_agents=1,
            observation_shape=(1, 3),
            egocentric_shape=(1, 1),
        ),
        agent_id=0,
    )

    assert policy.step(AgentObservation(agent_id=0, tokens=[])).name == "noop"
