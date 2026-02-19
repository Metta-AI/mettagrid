"""Tests for RandomMultiAgentPolicy with configurable vibe probability."""

from unittest.mock import MagicMock

import pytest

from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.policy.random_agent import RandomMultiAgentPolicy


def _policy_env_info(*, primary: list[str], vibe: list[str]) -> PolicyEnvInterface:
    return PolicyEnvInterface(
        obs_features=[],
        tags=[],
        action_names=primary,
        vibe_action_names=vibe,
        num_agents=1,
        observation_shape=(1, 1),
        egocentric_shape=(1, 1),
    )


def test_default_vibe_probability():
    """Default vibe_action_p is 0.5."""
    env_info = _policy_env_info(primary=["noop"], vibe=["change_vibe_a"])

    policy = RandomMultiAgentPolicy(env_info)
    assert policy._vibe_action_p == 0.5


def test_vibe_action_p_passed_to_agent():
    """vibe_action_p kwarg is passed to agent policy."""
    env_info = _policy_env_info(primary=["noop"], vibe=["change_vibe_a"])

    policy = RandomMultiAgentPolicy(env_info, vibe_action_p=0.01)
    agent = policy.agent_policy(0)

    assert agent._vibe_action_p == 0.01


def test_only_primary_actions():
    """Works when no vibe actions exist."""
    env_info = _policy_env_info(primary=["noop", "move_north"], vibe=[])

    policy = RandomMultiAgentPolicy(env_info, vibe_action_p=0.5)
    agent = policy.agent_policy(0)

    # Should not raise - picks from primary actions.
    action = agent.step(MagicMock())
    assert action.name in ["noop", "move_north"]


def test_invalid_vibe_probability_rejected() -> None:
    env_info = _policy_env_info(primary=["noop"], vibe=["change_vibe_a"])

    with pytest.raises(ValueError, match="vibe_action_p"):
        RandomMultiAgentPolicy(env_info, vibe_action_p=1.5)
