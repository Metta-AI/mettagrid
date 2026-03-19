import pytest

from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    GameConfig,
    MettaGridConfig,
    MoveActionConfig,
    NoopActionConfig,
    ObsConfig,
    WallConfig,
)
from mettagrid.map_builder.random_map import RandomMapBuilder
from mettagrid.policy.policy import AgentPolicy, MultiAgentPolicy
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.runner.rollout import single_episode_rollout
from mettagrid.simulator.interface import AgentObservation
from mettagrid.types import Action


class _NoopAgentPolicy(AgentPolicy):
    def step(self, obs: AgentObservation) -> Action:
        _ = obs
        return Action(name="noop")


class _LifecycleRecordingPolicy(MultiAgentPolicy):
    def __init__(self, policy_env_info: PolicyEnvInterface, device: str = "cpu") -> None:
        super().__init__(policy_env_info, device=device)
        self.prepare_calls = []
        self.close_calls = []
        self._agent_policies = {}

    def prepare_episode(self, episode) -> None:
        self.prepare_calls.append(episode)

    def close_episode(self, episode) -> None:
        self.close_calls.append(episode)

    def agent_policy(self, agent_id: int) -> AgentPolicy:
        if agent_id not in self._agent_policies:
            self._agent_policies[agent_id] = _NoopAgentPolicy(self.policy_env_info)
        return self._agent_policies[agent_id]


class _FailingPreparePolicy(_LifecycleRecordingPolicy):
    def prepare_episode(self, episode) -> None:
        super().prepare_episode(episode)
        raise RuntimeError("prepare failed")


def _make_config(num_agents: int = 2, max_steps: int = 2) -> MettaGridConfig:
    return MettaGridConfig(
        game=GameConfig(
            num_agents=num_agents,
            obs=ObsConfig(width=3, height=3, num_tokens=50),
            max_steps=max_steps,
            actions=ActionsConfig(noop=NoopActionConfig(), move=MoveActionConfig()),
            objects={"wall": WallConfig()},
            map_builder=RandomMapBuilder.Config(width=7, height=5, agents=num_agents, seed=42),
        )
    )


def test_single_episode_rollout_calls_policy_prepare_and_close() -> None:
    env = _make_config(num_agents=2, max_steps=1)
    policy = _LifecycleRecordingPolicy(PolicyEnvInterface.from_mg_cfg(env))

    single_episode_rollout(
        [policy],
        [0, 0],
        env,
        seed=7,
        max_action_time_ms=1000,
        render_mode="none",
        autostart=False,
        capture_replay=False,
    )

    assert len(policy.prepare_calls) == 1
    assert len(policy.close_calls) == 1
    assert policy.prepare_calls[0].episode_id == policy.close_calls[0].episode_id
    assert policy.prepare_calls[0].agent_ids == (0, 1)
    assert policy.prepare_calls[0].game_rule_actions == tuple(policy.policy_env_info.all_action_names)


def test_single_episode_rollout_closes_already_prepared_policies_when_prepare_fails() -> None:
    env = _make_config(num_agents=2, max_steps=1)
    first_policy = _LifecycleRecordingPolicy(PolicyEnvInterface.from_mg_cfg(env))
    failing_policy = _FailingPreparePolicy(PolicyEnvInterface.from_mg_cfg(env))

    with pytest.raises(RuntimeError, match="prepare failed"):
        single_episode_rollout(
            [first_policy, failing_policy],
            [0, 1],
            env,
            seed=7,
            max_action_time_ms=1000,
            render_mode="none",
            autostart=False,
            capture_replay=False,
        )

    assert len(first_policy.prepare_calls) == 1
    assert len(first_policy.close_calls) == 1
    assert first_policy.prepare_calls[0].episode_id == first_policy.close_calls[0].episode_id
    assert len(failing_policy.prepare_calls) == 1
    assert failing_policy.close_calls == []
