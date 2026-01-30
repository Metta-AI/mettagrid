"""Tests for RandomMultiAgentPolicy with configurable vibe probability."""

from unittest.mock import MagicMock

from mettagrid.policy.random_agent import RandomMultiAgentPolicy


def test_default_vibe_probability():
    """Default vibe_action_p is 0.5."""
    mock = MagicMock()
    mock.action_names = ["noop", "change_vibe_a"]

    policy = RandomMultiAgentPolicy(mock)
    assert policy._vibe_action_p == 0.5


def test_vibe_action_p_passed_to_agent():
    """vibe_action_p kwarg is passed to agent policy."""
    mock = MagicMock()
    mock.action_names = ["noop", "change_vibe_a"]

    policy = RandomMultiAgentPolicy(mock, vibe_action_p=0.01)
    agent = policy.agent_policy(0)

    assert agent._vibe_action_p == 0.01


def test_only_non_vibe_actions():
    """Works when no vibe actions exist."""
    mock = MagicMock()
    mock.action_names = ["noop", "move_north"]

    policy = RandomMultiAgentPolicy(mock, vibe_action_p=0.5)
    agent = policy.agent_policy(0)

    # Should not raise - picks from non-vibe actions
    action = agent.step(MagicMock())
    assert action.name in ["noop", "move_north"]
