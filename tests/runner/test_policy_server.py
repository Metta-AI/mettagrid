import json
from unittest.mock import patch

import pytest

from mettagrid.config.id_map import ObservationFeatureSpec
from mettagrid.config.mettagrid_config import TalkConfig
from mettagrid.policy.policy import AgentPolicy, MultiAgentPolicy
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.protobuf.sim.policy_v1 import policy_pb2
from mettagrid.runner.policy_server.server import (
    AgentNotFoundError,
    EpisodeNotFoundError,
    LocalPolicyServer,
    UnknownActionError,
    UnsupportedObservationFormatError,
    encode_action_id,
)
from mettagrid.simulator import Action, AgentObservation, Location, VisibleTalk


class ConstantActionAgentPolicy(AgentPolicy):
    def __init__(self, policy_env_info: PolicyEnvInterface, action: Action):
        super().__init__(policy_env_info)
        self._action = action

    def step(self, obs: AgentObservation) -> Action:
        _ = obs
        return self._action


class ConstantActionPolicy(MultiAgentPolicy):
    def __init__(self, policy_env_info: PolicyEnvInterface, action: Action):
        super().__init__(policy_env_info)
        self._action = action

    def agent_policy(self, agent_id: int) -> AgentPolicy:
        _ = agent_id
        return ConstantActionAgentPolicy(self.policy_env_info, self._action)


class EchoTalkAgentPolicy(AgentPolicy):
    def __init__(self, policy_env_info: PolicyEnvInterface):
        super().__init__(policy_env_info)
        self.last_talk: list[VisibleTalk] = []

    def step(self, obs: AgentObservation) -> Action:
        self.last_talk = list(obs.talk)
        talk = self.last_talk[0].text if self.last_talk else None
        return Action(name="move", talk=talk)


class EchoTalkPolicy(MultiAgentPolicy):
    def __init__(self, policy_env_info: PolicyEnvInterface):
        super().__init__(policy_env_info)
        self._agent = EchoTalkAgentPolicy(policy_env_info)

    def agent_policy(self, agent_id: int) -> AgentPolicy:
        _ = agent_id
        return self._agent


class InfoActionAgentPolicy(AgentPolicy):
    def __init__(self, policy_env_info: PolicyEnvInterface):
        super().__init__(policy_env_info)

    def step(self, obs: AgentObservation) -> Action:
        self._infos = {"current_task": f"task-{obs.agent_id}", "agent_id": obs.agent_id}
        return Action(name="move")


class InfoActionPolicy(MultiAgentPolicy):
    def __init__(self, policy_env_info: PolicyEnvInterface):
        super().__init__(policy_env_info)
        self._agents: dict[int, InfoActionAgentPolicy] = {}

    def agent_policy(self, agent_id: int) -> AgentPolicy:
        return self._agents.setdefault(agent_id, InfoActionAgentPolicy(self.policy_env_info))


def _policy_env(with_vibes: bool = False, *, talk_enabled: bool = False) -> PolicyEnvInterface:
    return PolicyEnvInterface(
        obs_features=[ObservationFeatureSpec(id=1, name="health", normalization=1.0)],
        tags=[],
        action_names=["noop", "move"],
        vibe_action_names=["change_vibe_default", "change_vibe_miner"] if with_vibes else [],
        num_agents=1,
        observation_shape=(1, 3),
        egocentric_shape=(1, 1),
        talk=TalkConfig(enabled=talk_enabled, max_length=140, cooldown_steps=50),
    )


def _make_service() -> LocalPolicyServer:
    return LocalPolicyServer("fake://policy")


def _prepare(
    service: LocalPolicyServer,
    policy: MultiAgentPolicy,
    env: PolicyEnvInterface,
    episode_id: str = "ep-123",
    agent_ids: list[int] | None = None,
):
    req = policy_pb2.PreparePolicyRequest(
        episode_id=episode_id,
        game_rules=policy_pb2.GameRules(
            features=[
                policy_pb2.GameRules.Feature(id=f.id, name=f.name, normalization=f.normalization)
                for f in env.obs_features
            ],
            actions=[policy_pb2.GameRules.Action(id=i, name=name) for i, name in enumerate(env.all_action_names)],
        ),
        env_interface=env.to_proto(),
        agent_ids=agent_ids or [0],
        observations_format=policy_pb2.AgentObservations.Format.TRIPLET_V1,
    )
    with (
        patch("mettagrid.runner.policy_server.server.policy_spec_from_uri", return_value=None),
        patch("mettagrid.runner.policy_server.server.initialize_or_load_policy", return_value=policy),
    ):
        return service.prepare_policy(req)


def test_prepare_policy():
    service = _make_service()
    env = _policy_env()
    resp = _prepare(service, ConstantActionPolicy(env, Action(name="move")), env)
    assert resp == policy_pb2.PreparePolicyResponse()


def test_prepare_policy_unsupported_observation_format():
    service = _make_service()
    req = policy_pb2.PreparePolicyRequest(
        episode_id="ep-123",
        agent_ids=[0],
        observations_format=policy_pb2.AgentObservations.Format.AGENT_OBSERVATIONS_FORMAT_UNKNOWN,
    )
    with pytest.raises(UnsupportedObservationFormatError):
        service.prepare_policy(req)


def test_batch_step():
    service = _make_service()
    env = _policy_env()
    _prepare(service, ConstantActionPolicy(env, Action(name="move")), env)

    req = policy_pb2.BatchStepRequest(
        episode_id="ep-123",
        step_id=1,
        agent_observations=[policy_pb2.AgentObservations(agent_id=0, observations=b"")],
    )
    resp = service.batch_step(req)

    assert len(resp.agent_actions) == 1
    assert resp.agent_actions[0].agent_id == 0
    assert list(resp.agent_actions[0].action_id) == [1]


def test_batch_step_dual_action_encodes_core_and_vibe():
    service = _make_service()
    env = _policy_env(with_vibes=True)
    _prepare(service, ConstantActionPolicy(env, Action(name="move", vibe="change_vibe_miner")), env)

    req = policy_pb2.BatchStepRequest(
        episode_id="ep-123",
        step_id=1,
        agent_observations=[policy_pb2.AgentObservations(agent_id=0, observations=b"")],
    )
    resp = service.batch_step(req)

    assert len(resp.agent_actions) == 1
    assert resp.agent_actions[0].agent_id == 0
    assert list(resp.agent_actions[0].action_id) == [7]


def test_batch_step_vibe_only_action_encodes_vibe_range():
    service = _make_service()
    env = _policy_env(with_vibes=True)
    _prepare(service, ConstantActionPolicy(env, Action(name="change_vibe_miner")), env)

    req = policy_pb2.BatchStepRequest(
        episode_id="ep-123",
        step_id=1,
        agent_observations=[policy_pb2.AgentObservations(agent_id=0, observations=b"")],
    )
    resp = service.batch_step(req)

    assert len(resp.agent_actions) == 1
    assert resp.agent_actions[0].agent_id == 0
    assert list(resp.agent_actions[0].action_id) == [3]


def test_batch_step_unknown_episode():
    service = _make_service()
    req = policy_pb2.BatchStepRequest(
        episode_id="nonexistent",
        step_id=1,
        agent_observations=[],
    )
    with pytest.raises(EpisodeNotFoundError):
        service.batch_step(req)


def test_batch_step_unknown_agent():
    service = _make_service()
    env = _policy_env()
    _prepare(service, ConstantActionPolicy(env, Action(name="move")), env, agent_ids=[0])

    req = policy_pb2.BatchStepRequest(
        episode_id="ep-123",
        step_id=1,
        agent_observations=[policy_pb2.AgentObservations(agent_id=99, observations=b"")],
    )
    with pytest.raises(AgentNotFoundError):
        service.batch_step(req)


def test_batch_step_unknown_action_raises():
    service = _make_service()
    env = _policy_env()
    _prepare(service, ConstantActionPolicy(env, Action(name="unknown_action")), env)

    req = policy_pb2.BatchStepRequest(
        episode_id="ep-123",
        step_id=1,
        agent_observations=[policy_pb2.AgentObservations(agent_id=0, observations=b"")],
    )
    with pytest.raises(UnknownActionError):
        service.batch_step(req)


def test_encode_action_id_encodes_plain_action() -> None:
    env = _policy_env()
    assert encode_action_id(Action(name="move"), env) == 1


def test_batch_step_round_trips_visible_talk_and_talk_text() -> None:
    service = _make_service()
    env = _policy_env(talk_enabled=True)
    policy = EchoTalkPolicy(env)
    _prepare(service, policy, env)

    req = policy_pb2.BatchStepRequest(
        episode_id="ep-123",
        step_id=1,
        agent_observations=[
            policy_pb2.AgentObservations(
                agent_id=0,
                observations=b"",
                visible_talk=[
                    policy_pb2.VisibleTalk(
                        agent_id=7,
                        row=2,
                        col=3,
                        remaining_steps=11,
                        text="hold east",
                    )
                ],
            )
        ],
    )
    resp = service.batch_step(req)

    assert policy._agent.last_talk == [
        VisibleTalk(
            agent_id=7,
            text="hold east",
            location=Location(row=2, col=3),
            remaining_steps=11,
        )
    ]
    assert len(resp.agent_actions) == 1
    assert list(resp.agent_actions[0].action_id) == [1]
    assert resp.agent_actions[0].talk_text == "hold east"


def test_batch_step_serializes_policy_infos() -> None:
    service = _make_service()
    env = _policy_env()
    _prepare(service, InfoActionPolicy(env), env)

    req = policy_pb2.BatchStepRequest(
        episode_id="ep-123",
        step_id=1,
        agent_observations=[policy_pb2.AgentObservations(agent_id=0, observations=b"")],
    )
    resp = service.batch_step(req)

    assert json.loads(resp.agent_actions[0].infos_json) == {"current_task": "task-0", "agent_id": 0}
