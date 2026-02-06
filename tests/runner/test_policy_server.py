import pytest

from mettagrid.policy.policy import AgentPolicy, MultiAgentPolicy
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.protobuf.sim.policy_v1 import policy_pb2
from mettagrid.runner.policy_server.server import (
    AgentNotFoundError,
    EpisodeNotFoundError,
    LocalPolicyServer,
    UnsupportedObservationFormatError,
)
from mettagrid.simulator import Action, AgentObservation


def null_env_adapter(_: policy_pb2.PreparePolicyRequest) -> PolicyEnvInterface:
    return None  # type: ignore[return-value]


class ConstantActionAgentPolicy(AgentPolicy):
    def __init__(self, action_id: int):
        self.action_id = action_id

    def step(self, obs: AgentObservation) -> Action:
        return Action(name=str(self.action_id))


class ConstantActionPolicy(MultiAgentPolicy):
    def __init__(self, action_id: int):
        self.action_id = action_id

    def agent_policy(self, agent_id: int) -> AgentPolicy:
        return ConstantActionAgentPolicy(self.action_id)


def _make_service(action_id: int = 42) -> LocalPolicyServer:
    return LocalPolicyServer(lambda _: ConstantActionPolicy(action_id), null_env_adapter)


def _prepare(service: LocalPolicyServer, episode_id: str = "ep-123", agent_ids: list[int] | None = None):
    req = policy_pb2.PreparePolicyRequest(
        episode_id=episode_id,
        game_rules=policy_pb2.GameRules(
            features=[policy_pb2.GameRules.Feature(id=1, name="health", normalization=1.0)],
            actions=[policy_pb2.GameRules.Action(id=42, name="42")],
        ),
        agent_ids=agent_ids or [0],
        observations_format=policy_pb2.AgentObservations.Format.TRIPLET_V1,
    )
    return service.prepare_policy(req)


def test_prepare_policy():
    service = _make_service()
    resp = _prepare(service)
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
    _prepare(service)

    req = policy_pb2.BatchStepRequest(
        episode_id="ep-123",
        step_id=1,
        agent_observations=[policy_pb2.AgentObservations(agent_id=0, observations=b"")],
    )
    resp = service.batch_step(req)

    assert len(resp.agent_actions) == 1
    assert resp.agent_actions[0].agent_id == 0
    assert list(resp.agent_actions[0].action_id) == [42]


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
    _prepare(service, agent_ids=[0])

    req = policy_pb2.BatchStepRequest(
        episode_id="ep-123",
        step_id=1,
        agent_observations=[policy_pb2.AgentObservations(agent_id=99, observations=b"")],
    )
    with pytest.raises(AgentNotFoundError):
        service.batch_step(req)
