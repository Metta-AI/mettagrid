import tempfile
import threading
import time

from mettagrid.config.id_map import ObservationFeatureSpec
from mettagrid.policy.policy import AgentPolicy, MultiAgentPolicy
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.runner.policy_server.server import LocalPolicyServer
from mettagrid.runner.policy_server.socket_transport import (
    SocketPolicyServer,
    SocketPolicyServerClient,
    _serialize_triplet_v1,
)
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


def _run_socket_test(action_name: str, test_fn):
    env = _env_interface()
    service = LocalPolicyServer(
        lambda env_info: _ConstantPolicy(env_info, action_name),
        lambda _: env,
    )
    # Use /tmp directly for short socket paths
    socket_path = tempfile.mktemp(prefix="test-policy-", suffix=".sock", dir="/tmp")
    server = SocketPolicyServer(service, socket_path)

    server_thread = threading.Thread(target=server.serve, daemon=True)
    server_thread.start()

    for _ in range(100):
        try:
            client = SocketPolicyServerClient(env, socket_path=socket_path)
            break
        except (ConnectionRefusedError, FileNotFoundError):
            time.sleep(0.01)
    else:
        raise RuntimeError("Could not connect to socket server")

    try:
        test_fn(client, env)
    finally:
        client.close()
        server_thread.join(timeout=2)


def test_socket_policy_step_returns_correct_action():
    def check(client: SocketPolicyServerClient, env: PolicyEnvInterface):
        agent = client.agent_policy(0)
        obs = AgentObservation(agent_id=0, tokens=[])
        action = agent.step(obs)
        assert action.name == "move"

    _run_socket_test("move", check)


def test_socket_policy_step_with_observations():
    token = ObservationToken(
        feature=ObservationFeatureSpec(id=1, name="health", normalization=1.0),
        value=42,
        raw_token=(0x11, 1, 42),
    )

    def check(client: SocketPolicyServerClient, env: PolicyEnvInterface):
        agent = client.agent_policy(0)
        obs = AgentObservation(agent_id=0, tokens=[token])
        action = agent.step(obs)
        assert action.name == "move"

    _run_socket_test("move", check)


def test_socket_policy_multiple_agents():
    def check(client: SocketPolicyServerClient, env: PolicyEnvInterface):
        agent0 = client.agent_policy(0)
        agent1 = client.agent_policy(1)
        obs0 = AgentObservation(agent_id=0, tokens=[])
        obs1 = AgentObservation(agent_id=1, tokens=[])
        action0 = agent0.step(obs0)
        action1 = agent1.step(obs1)
        assert action0.name == "noop"
        assert action1.name == "noop"

    _run_socket_test("noop", check)


def test_agent_policy_deduplicates():
    def check(client: SocketPolicyServerClient, env: PolicyEnvInterface):
        a1 = client.agent_policy(0)
        a2 = client.agent_policy(0)
        assert a1 is a2
        assert len(client._agents) == 1

    _run_socket_test("move", check)


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
