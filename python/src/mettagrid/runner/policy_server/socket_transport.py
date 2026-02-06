import logging
import os
import socket
import struct

from google.protobuf import json_format

from mettagrid.policy.policy import AgentPolicy, MultiAgentPolicy
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.protobuf.sim.policy_v1 import policy_pb2
from mettagrid.runner.policy_server.server import LocalPolicyServer
from mettagrid.simulator import Action, AgentObservation

logger = logging.getLogger(__name__)

_HEADER_SIZE = 4


class PolicyStepError(Exception):
    pass


def _serialize_triplet_v1(obs: AgentObservation) -> bytes:
    buf = bytearray()
    for token in obs.tokens:
        loc_byte, feature_id, value = token.raw_token
        buf.extend((loc_byte, feature_id, value))
    return bytes(buf)


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise EOFError("connection closed")
        buf.extend(chunk)
    return bytes(buf)


def _send_length_prefixed(sock: socket.socket, data: bytes) -> None:
    sock.sendall(struct.pack("<I", len(data)) + data)


def _recv_length_prefixed(sock: socket.socket) -> bytes:
    header = _recv_exact(sock, _HEADER_SIZE)
    length = struct.unpack("<I", header)[0]
    return _recv_exact(sock, length)


class SocketPolicyServer:
    def __init__(self, service: LocalPolicyServer, socket_path: str, ready_file: str | None = None):
        self._service = service
        self._socket_path = socket_path
        self._ready_file = ready_file

    def serve(self) -> None:
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            os.unlink(self._socket_path)
        except FileNotFoundError:
            pass
        srv.bind(self._socket_path)
        srv.listen(1)
        logger.info("Socket policy server listening on %s", self._socket_path)

        if self._ready_file is not None:
            with open(self._ready_file, "w") as f:
                f.write("ready")

        conn, _ = srv.accept()
        logger.info("Socket policy server accepted connection")
        try:
            self._handle_connection(conn)
        except EOFError:
            logger.info("Client disconnected, shutting down")
        finally:
            conn.close()
            srv.close()

    def _handle_connection(self, conn: socket.socket) -> None:
        prepare_json = _recv_length_prefixed(conn)
        req = json_format.Parse(prepare_json, policy_pb2.PreparePolicyRequest())
        resp = self._service.prepare_policy(req)
        resp_json = json_format.MessageToJson(resp).encode()
        _send_length_prefixed(conn, resp_json)

        while True:
            header = _recv_exact(conn, 8)
            agent_id = struct.unpack("<i", header[:4])[0]
            obs_len = struct.unpack("<I", header[4:8])[0]
            obs_bytes = _recv_exact(conn, obs_len) if obs_len > 0 else b""

            step_req = policy_pb2.BatchStepRequest(
                episode_id=req.episode_id,
                step_id=0,
                agent_observations=[
                    policy_pb2.AgentObservations(agent_id=agent_id, observations=obs_bytes),
                ],
            )
            step_resp = self._service.batch_step(step_req)

            action_id = 0
            if step_resp.agent_actions and step_resp.agent_actions[0].action_id:
                action_id = step_resp.agent_actions[0].action_id[0]
            conn.sendall(struct.pack("<i", action_id))


class SocketPolicyServerClient(MultiAgentPolicy):
    def __init__(self, policy_env_info: PolicyEnvInterface, *, socket_path: str):
        super().__init__(policy_env_info)
        self._socket_path = socket_path
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.connect(socket_path)
        self._agents: dict[int, SocketPolicyServerAgentClient] = {}
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
            episode_id="socket-episode",
            game_rules=game_rules,
            agent_ids=agent_ids,
            observations_format=policy_pb2.AgentObservations.Format.TRIPLET_V1,
            env_interface=self._policy_env_info.to_proto(),
        )
        req_json = json_format.MessageToJson(req).encode()
        _send_length_prefixed(self._sock, req_json)
        _recv_length_prefixed(self._sock)

    def step_agent(self, agent_id: int, obs_bytes: bytes) -> int:
        header = struct.pack("<iI", agent_id, len(obs_bytes))
        self._sock.sendall(header + obs_bytes)
        resp = _recv_exact(self._sock, 4)
        return struct.unpack("<i", resp)[0]

    def agent_policy(self, agent_id: int) -> AgentPolicy:
        if agent_id not in self._agents:
            self._agents[agent_id] = SocketPolicyServerAgentClient(self, agent_id)
        return self._agents[agent_id]

    def reset(self) -> None:
        self._agents.clear()

    def close(self) -> None:
        self._sock.close()

    def __enter__(self) -> "SocketPolicyServerClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class SocketPolicyServerAgentClient(AgentPolicy):
    def __init__(self, parent: SocketPolicyServerClient, agent_id: int):
        super().__init__(parent.policy_env_info)
        self._parent = parent
        self._agent_id = agent_id

    def step(self, obs: AgentObservation) -> Action:
        obs_bytes = _serialize_triplet_v1(obs)
        try:
            action_id = self._parent.step_agent(self._agent_id, obs_bytes)
        except (EOFError, OSError) as e:
            raise PolicyStepError(f"Socket communication failed for agent {self._agent_id}") from e
        action_names = self._parent.policy_env_info.action_names
        if 0 <= action_id < len(action_names):
            return Action(name=action_names[action_id])
        return Action(name="noop")
