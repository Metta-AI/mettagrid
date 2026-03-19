import json
import threading
import time
from collections.abc import Callable
from unittest.mock import patch

from websockets.exceptions import ConnectionClosed
from websockets.sync.server import serve as ws_serve

from mettagrid.config.id_map import ObservationFeatureSpec
from mettagrid.policy.policy import MultiAgentPolicy
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.policy.streaming_controller import StreamingControllerPolicy
from mettagrid.protobuf.sim.policy_v1 import policy_pb2
from mettagrid.runner.policy_server.server import LocalPolicyServer

NOOP_POLICY_SOURCE = """
def step(agent_id, observation, state, policy_env):
    return {"action": "noop", "logs": [{"kind": "local", "event": "noop"}]}
""".strip()

MOVE_POLICY_SOURCE = """
def step(agent_id, observation, state, policy_env):
    return {"action": "move", "logs": [{"kind": "remote", "event": "move"}]}
""".strip()

INVALID_POLICY_SOURCE = """
def not_step(agent_id, observation, state, policy_env):
    return {"action": "move"}
""".strip()

CRASHING_POLICY_SOURCE = """
def step(agent_id, observation, state, policy_env):
    raise RuntimeError("boom")
""".strip()

BAD_DECISION_POLICY_SOURCE = """
def step(agent_id, observation, state, policy_env):
    return {"action": 1}
""".strip()


def _policy_env() -> PolicyEnvInterface:
    return PolicyEnvInterface(
        obs_features=[ObservationFeatureSpec(id=1, name="health", normalization=1.0)],
        tags=[],
        action_names=["noop", "move"],
        vibe_action_names=[],
        num_agents=1,
        observation_shape=(1, 3),
        egocentric_shape=(1, 1),
    )


def _prepare(service: LocalPolicyServer, policy: MultiAgentPolicy, env: PolicyEnvInterface, episode_id: str) -> None:
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
        agent_ids=[0],
        observations_format=policy_pb2.AgentObservations.Format.TRIPLET_V1,
    )
    with (
        patch("mettagrid.runner.policy_server.server.policy_spec_from_uri", return_value=None),
        patch("mettagrid.runner.policy_server.server.initialize_or_load_policy", return_value=policy),
    ):
        service.prepare_policy(req)


def _step(service: LocalPolicyServer, episode_id: str) -> list[int]:
    resp = service.batch_step(
        policy_pb2.BatchStepRequest(
            episode_id=episode_id,
            step_id=1,
            agent_observations=[policy_pb2.AgentObservations(agent_id=0, observations=b"\x11\x01\x2a")],
        )
    )
    return list(resp.agent_actions[0].action_id)


def _wait_until(predicate: Callable[[], bool], timeout_seconds: float = 1.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    assert predicate()


def _start_controller(handler: Callable) -> tuple[str, Callable[[], None]]:
    ready = threading.Event()
    holder: dict[str, object] = {}

    def run() -> None:
        with ws_serve(handler, "127.0.0.1", 0) as server:
            holder["server"] = server
            holder["port"] = server.socket.getsockname()[1]
            ready.set()
            server.serve_forever()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    ready.wait(timeout=2)
    assert "port" in holder

    def stop() -> None:
        server = holder["server"]
        assert server is not None
        server.shutdown()
        thread.join(timeout=2)

    return f"ws://127.0.0.1:{holder['port']}", stop


def test_streaming_controller_connects_during_prepare_and_applies_initial_patch():
    received: list[dict] = []

    def handler(ws) -> None:
        try:
            message = ws.recv()
            assert isinstance(message, str)
            received.append(json.loads(message))
            ws.send(json.dumps({"kind": "patch", "set_policy": MOVE_POLICY_SOURCE}))
            while True:
                followup = ws.recv(timeout=0.5)
                if isinstance(followup, str):
                    received.append(json.loads(followup))
        except ConnectionClosed:
            return

    controller_url, stop_controller = _start_controller(handler)
    env = _policy_env()
    policy = StreamingControllerPolicy(
        env,
        controller_url=controller_url,
        initial_policy_source=NOOP_POLICY_SOURCE,
    )
    service = LocalPolicyServer("fake://policy")

    try:
        _prepare(service, policy, env, episode_id="ep-streaming-prepare")
        assert _step(service, "ep-streaming-prepare") == [1]
        _wait_until(lambda: len(received) >= 2)
    finally:
        service.close_episode("ep-streaming-prepare")
        stop_controller()

    assert received[0]["kind"] == "episode_hello"
    assert received[0]["episode_id"] == "ep-streaming-prepare"
    assert received[0]["agent_ids"] == [0]
    assert received[1]["kind"] == "step"
    assert received[1]["decision"]["action"] == "move"
    assert received[1]["logs"] == [{"kind": "remote", "event": "move"}]


def test_streaming_controller_keeps_last_good_policy_after_invalid_patch():
    received: list[dict] = []
    sent_invalid_patch = threading.Event()

    def handler(ws) -> None:
        try:
            message = ws.recv()
            assert isinstance(message, str)
            received.append(json.loads(message))
            while True:
                followup = ws.recv(timeout=0.5)
                if not isinstance(followup, str):
                    continue
                payload = json.loads(followup)
                received.append(payload)
                if payload["kind"] == "step" and not sent_invalid_patch.is_set():
                    ws.send(json.dumps({"kind": "patch", "set_policy": INVALID_POLICY_SOURCE}))
                    sent_invalid_patch.set()
        except ConnectionClosed:
            return

    controller_url, stop_controller = _start_controller(handler)
    env = _policy_env()
    policy = StreamingControllerPolicy(
        env,
        controller_url=controller_url,
        initial_policy_source=NOOP_POLICY_SOURCE,
    )
    service = LocalPolicyServer("fake://policy")

    try:
        _prepare(service, policy, env, episode_id="ep-invalid-patch")
        assert _step(service, "ep-invalid-patch") == [0]
        _wait_until(sent_invalid_patch.is_set)
        assert _step(service, "ep-invalid-patch") == [0]
    finally:
        service.close_episode("ep-invalid-patch")
        stop_controller()

    step_messages = [payload for payload in received if payload["kind"] == "step"]
    assert [payload["decision"]["action"] for payload in step_messages] == ["noop", "noop"]


def test_streaming_controller_reverts_patch_that_crashes_during_step():
    sent_crashing_patch = threading.Event()

    def handler(ws) -> None:
        try:
            message = ws.recv()
            assert isinstance(message, str)
            while True:
                followup = ws.recv(timeout=0.5)
                if not isinstance(followup, str):
                    continue
                payload = json.loads(followup)
                if payload["kind"] == "step" and not sent_crashing_patch.is_set():
                    ws.send(json.dumps({"kind": "patch", "set_policy": CRASHING_POLICY_SOURCE}))
                    sent_crashing_patch.set()
        except ConnectionClosed:
            return

    controller_url, stop_controller = _start_controller(handler)
    env = _policy_env()
    policy = StreamingControllerPolicy(
        env,
        controller_url=controller_url,
        initial_policy_source=NOOP_POLICY_SOURCE,
    )
    service = LocalPolicyServer("fake://policy")

    try:
        _prepare(service, policy, env, episode_id="ep-crashing-patch")
        assert _step(service, "ep-crashing-patch") == [0]
        _wait_until(sent_crashing_patch.is_set)
        assert _step(service, "ep-crashing-patch") == [0]
    finally:
        service.close_episode("ep-crashing-patch")
        stop_controller()


def test_streaming_controller_reverts_patch_with_invalid_decision():
    sent_bad_patch = threading.Event()

    def handler(ws) -> None:
        try:
            message = ws.recv()
            assert isinstance(message, str)
            while True:
                followup = ws.recv(timeout=0.5)
                if not isinstance(followup, str):
                    continue
                payload = json.loads(followup)
                if payload["kind"] == "step" and not sent_bad_patch.is_set():
                    ws.send(json.dumps({"kind": "patch", "set_policy": BAD_DECISION_POLICY_SOURCE}))
                    sent_bad_patch.set()
        except ConnectionClosed:
            return

    controller_url, stop_controller = _start_controller(handler)
    env = _policy_env()
    policy = StreamingControllerPolicy(
        env,
        controller_url=controller_url,
        initial_policy_source=NOOP_POLICY_SOURCE,
    )
    service = LocalPolicyServer("fake://policy")

    try:
        _prepare(service, policy, env, episode_id="ep-bad-decision-patch")
        assert _step(service, "ep-bad-decision-patch") == [0]
        _wait_until(sent_bad_patch.is_set)
        assert _step(service, "ep-bad-decision-patch") == [0]
    finally:
        service.close_episode("ep-bad-decision-patch")
        stop_controller()
