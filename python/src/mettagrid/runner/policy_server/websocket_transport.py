import logging
import struct
import threading
from typing import Any

from google.protobuf import json_format
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect as ws_connect
from websockets.sync.server import serve as ws_serve

from mettagrid.policy.policy import AgentPolicy, MultiAgentPolicy
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.protobuf.sim.policy_v1 import policy_pb2
from mettagrid.runner.policy_server.server import LocalPolicyServer
from mettagrid.simulator import Action, AgentObservation

logger = logging.getLogger(__name__)

PREPARE_TIMEOUT = 300.0


class PolicyStepError(Exception):
    pass


def _serialize_triplet_v1(obs: AgentObservation) -> bytes:
    buf = bytearray()
    for token in obs.tokens:
        loc_byte, feature_id, value = token.raw_token
        buf.extend((loc_byte, feature_id, value))
    return bytes(buf)


class WebSocketPolicyServer:
    def __init__(
        self,
        service: LocalPolicyServer,
        host: str = "127.0.0.1",
        port: int = 0,
        ready_file: str | None = None,
    ):
        self._service = service
        self._host = host
        self._port = port
        self._ready_file = ready_file
        self._ready_event = threading.Event()
        self._actual_port = 0
        self._ws_server: Any = None

    @property
    def port(self) -> int:
        self._ready_event.wait()
        return self._actual_port

    def serve(self) -> None:
        with ws_serve(self._handler, self._host, self._port) as server:
            self._ws_server = server
            self._actual_port = server.socket.getsockname()[1]
            logger.info("WebSocket policy server listening on %s:%d", self._host, self._actual_port)

            if self._ready_file is not None:
                with open(self._ready_file, "w") as f:
                    f.write(str(self._actual_port))

            self._ready_event.set()
            server.serve_forever()

    def _handler(self, ws) -> None:
        try:
            prepare_json = ws.recv()
            req = json_format.Parse(prepare_json, policy_pb2.PreparePolicyRequest())
            resp = self._service.prepare_policy(req)
            ws.send(json_format.MessageToJson(resp))

            for message in ws:
                agent_id = struct.unpack("<i", message[:4])[0]
                obs_bytes = message[4:]

                step_req = policy_pb2.BatchStepRequest(
                    episode_id=req.episode_id,
                    step_id=0,
                    agent_observations=[
                        policy_pb2.AgentObservations(agent_id=agent_id, observations=obs_bytes),
                    ],
                )
                step_resp = self._service.batch_step(step_req)

                ws.send(struct.pack("<i", step_resp.agent_actions[0].action_id[0]))
        finally:
            logger.info("Client disconnected, shutting down")
            self._ws_server.shutdown()


class WebSocketPolicyServerClient(MultiAgentPolicy):
    def __init__(self, policy_env_info: PolicyEnvInterface, *, url: str):
        super().__init__(policy_env_info)
        self._url = url
        self._ws = ws_connect(url, open_timeout=PREPARE_TIMEOUT)
        self._agents: dict[int, WebSocketPolicyServerAgentClient] = {}
        self._prepare(list(range(policy_env_info.num_agents)))

    def _prepare(self, agent_ids: list[int]) -> None:
        game_rules = policy_pb2.GameRules(
            features=[
                policy_pb2.GameRules.Feature(id=f.id, name=f.name, normalization=f.normalization)
                for f in self._policy_env_info.obs_features
            ],
            actions=[
                policy_pb2.GameRules.Action(id=i, name=name)
                for i, name in enumerate(self._policy_env_info.action_names)
            ],
        )
        req = policy_pb2.PreparePolicyRequest(
            episode_id="ws-episode",
            game_rules=game_rules,
            agent_ids=agent_ids,
            observations_format=policy_pb2.AgentObservations.Format.TRIPLET_V1,
            env_interface=self._policy_env_info.to_proto(),
        )
        logger.info("Sending prepare policy request to policy server for %s", self._url)
        self._ws.send(json_format.MessageToJson(req))
        logger.info("Waiting for prepare policy response from policy server for %s", self._url)
        self._ws.recv(timeout=PREPARE_TIMEOUT)
        logger.info("Received prepare policy response from policy server for %s", self._url)

    def step_agent(self, agent_id: int, obs_bytes: bytes) -> int:
        self._ws.send(struct.pack("<i", agent_id) + obs_bytes)
        resp: bytes = self._ws.recv()  # type: ignore[assignment]
        return struct.unpack("<i", resp)[0]

    def agent_policy(self, agent_id: int) -> AgentPolicy:
        if agent_id not in self._agents:
            self._agents[agent_id] = WebSocketPolicyServerAgentClient(self, agent_id)
        return self._agents[agent_id]

    def reset(self) -> None:
        self._agents.clear()

    def close(self) -> None:
        self._ws.close()

    def __enter__(self) -> "WebSocketPolicyServerClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class WebSocketPolicyServerAgentClient(AgentPolicy):
    def __init__(self, parent: WebSocketPolicyServerClient, agent_id: int):
        super().__init__(parent.policy_env_info)
        self._parent = parent
        self._agent_id = agent_id

    def step(self, obs: AgentObservation) -> Action:
        obs_bytes = _serialize_triplet_v1(obs)
        try:
            action_id = self._parent.step_agent(self._agent_id, obs_bytes)
        except (ConnectionClosed, EOFError, OSError) as e:
            raise PolicyStepError(f"WebSocket communication failed for agent {self._agent_id}") from e
        action_names = self._parent.policy_env_info.action_names
        if not (0 <= action_id < len(action_names)):
            raise PolicyStepError(f"Policy server returned invalid action_id {action_id} for agent {self._agent_id}")
        return Action(name=action_names[action_id])
