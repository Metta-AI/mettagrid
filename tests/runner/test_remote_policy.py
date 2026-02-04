import urllib.parse
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from mettagrid.config.id_map import ObservationFeatureSpec
from mettagrid.policy.policy import AgentPolicy, MultiAgentPolicy
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.runner.remote import RemoteMultiAgentPolicy, _serialize_triplet_v1
from mettagrid.runner.serve_policy import PolicyService, create_app
from mettagrid.simulator import Action, AgentObservation, ObservationToken


def _env_interface() -> PolicyEnvInterface:
    return PolicyEnvInterface(
        obs_features=[ObservationFeatureSpec(id=1, name="health", normalization=1.0)],
        tags=[],
        action_names=["noop", "move"],
        num_agents=2,
        observation_shape=(1, 3),
        egocentric_shape=(1, 1),
    )


class _ConstantAgentPolicy(AgentPolicy):
    def __init__(self, policy_env_info: PolicyEnvInterface, action_name: str):
        super().__init__(policy_env_info)
        self._action_name = action_name

    def step(self, _obs: AgentObservation) -> Action:
        return Action(name=self._action_name)


class _ConstantPolicy(MultiAgentPolicy):
    def __init__(self, policy_env_info: PolicyEnvInterface, action_name: str):
        super().__init__(policy_env_info)
        self._action_name = action_name

    def agent_policy(self, _agent_id: int) -> AgentPolicy:
        return _ConstantAgentPolicy(self._policy_env_info, self._action_name)


def _make_test_client(action_name: str = "move") -> TestClient:
    service = PolicyService(
        lambda env: _ConstantPolicy(env, action_name),
        lambda _: _env_interface(),
    )
    return TestClient(create_app(service))


def _patch_httpx_with_test_client(test_client: TestClient):
    class _MockResponse:
        def __init__(self, starlette_resp):
            self._resp = starlette_resp
            self.status_code = starlette_resp.status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"HTTP {self.status_code}",
                    request=httpx.Request("POST", "http://fake"),
                    response=httpx.Response(self.status_code),
                )

        def json(self):
            return self._resp.json()

    class _MockClient:
        def post(self, url, *, json=None, timeout=None):
            path = urllib.parse.urlparse(url).path
            return _MockResponse(test_client.post(path, json=json))

        def close(self):
            pass

    return patch("mettagrid.runner.remote.httpx.Client", return_value=_MockClient())


def test_remote_policy_step_returns_correct_action():
    client = _make_test_client("move")
    env = _env_interface()

    with _patch_httpx_with_test_client(client):
        policy = RemoteMultiAgentPolicy(env, base_url="http://fake:1234")
        agent = policy.agent_policy(0)
        obs = AgentObservation(agent_id=0, tokens=[])
        action = agent.step(obs)

    assert action.name == "move"


def test_remote_policy_step_with_observations():
    client = _make_test_client("move")
    env = _env_interface()

    token = ObservationToken(
        feature=ObservationFeatureSpec(id=1, name="health", normalization=1.0),
        value=42,
        raw_token=(0x11, 1, 42),
    )

    with _patch_httpx_with_test_client(client):
        policy = RemoteMultiAgentPolicy(env, base_url="http://fake:1234")
        agent = policy.agent_policy(0)
        obs = AgentObservation(agent_id=0, tokens=[token])
        action = agent.step(obs)

    assert action.name == "move"


def test_remote_policy_multiple_agents():
    client = _make_test_client("noop")
    env = _env_interface()

    with _patch_httpx_with_test_client(client):
        policy = RemoteMultiAgentPolicy(env, base_url="http://fake:1234")
        agent0 = policy.agent_policy(0)
        agent1 = policy.agent_policy(1)
        obs0 = AgentObservation(agent_id=0, tokens=[])
        obs1 = AgentObservation(agent_id=1, tokens=[])
        action0 = agent0.step(obs0)
        action1 = agent1.step(obs1)

    assert action0.name == "noop"
    assert action1.name == "noop"


def test_agent_policy_deduplicates():
    client = _make_test_client()
    env = _env_interface()

    with _patch_httpx_with_test_client(client):
        policy = RemoteMultiAgentPolicy(env, base_url="http://fake:1234")
        a1 = policy.agent_policy(0)
        a2 = policy.agent_policy(0)

    assert a1 is a2
    assert len(policy._agents) == 1


def test_serialize_triplet_v1_empty():
    obs = AgentObservation(agent_id=0, tokens=[])
    assert _serialize_triplet_v1(obs) == b""


def test_serialize_triplet_v1_single_token():
    token = ObservationToken(
        feature=ObservationFeatureSpec(id=1, name="health", normalization=1.0),
        value=42,
        raw_token=(0x11, 1, 42),
    )
    obs = AgentObservation(agent_id=0, tokens=[token])
    result = _serialize_triplet_v1(obs)
    assert result == bytes([0x11, 1, 42])


def test_serialize_triplet_v1_multiple_tokens():
    tokens = [
        ObservationToken(
            feature=ObservationFeatureSpec(id=1, name="health", normalization=1.0),
            value=10,
            raw_token=(0x01, 1, 10),
        ),
        ObservationToken(
            feature=ObservationFeatureSpec(id=2, name="energy", normalization=1.0),
            value=20,
            raw_token=(0x02, 2, 20),
        ),
    ]
    obs = AgentObservation(agent_id=0, tokens=tokens)
    result = _serialize_triplet_v1(obs)
    assert result == bytes([0x01, 1, 10, 0x02, 2, 20])
