import logging
import threading
from collections.abc import Sequence
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


def _decode_action_id(action_id: int, policy_env_info: PolicyEnvInterface) -> Action:
    primary_action_names = policy_env_info.action_names
    vibe_action_names = policy_env_info.vibe_action_names
    num_primary_actions = len(primary_action_names)
    num_vibe_actions = len(vibe_action_names)

    if action_id < 0:
        raise PolicyStepError(f"Policy server returned invalid action_id {action_id}")

    if action_id < num_primary_actions:
        return Action(name=primary_action_names[action_id])

    if num_vibe_actions <= 0:
        raise PolicyStepError(
            f"Policy server returned invalid action_id {action_id}; expected range [0, {num_primary_actions - 1}]"
        )

    if action_id < num_primary_actions + num_vibe_actions:
        vibe_index = action_id - num_primary_actions
        return Action(name=vibe_action_names[vibe_index])

    encoded = action_id - num_primary_actions - num_vibe_actions
    max_encoded = num_primary_actions * num_vibe_actions
    if encoded >= max_encoded:
        raise PolicyStepError(
            "Policy server returned invalid action_id "
            f"{action_id}; expected range [0, {num_primary_actions + num_vibe_actions + max_encoded - 1}]"
        )

    primary_index = encoded // num_vibe_actions
    vibe_index = encoded % num_vibe_actions
    return Action(name=primary_action_names[primary_index], vibe=vibe_action_names[vibe_index])


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
        episode_id: str | None = None
        try:
            prepare_json = ws.recv()
            if not isinstance(prepare_json, str):
                raise PolicyStepError("Expected JSON prepare message")
            req = json_format.Parse(prepare_json, policy_pb2.PreparePolicyRequest())
            episode_id = req.episode_id
            resp = self._service.prepare_policy(req)
            ws.send(json_format.MessageToJson(resp))

            for message in ws:
                if not isinstance(message, bytes):
                    raise PolicyStepError("Expected binary BatchStepRequest message")
                step_req = policy_pb2.BatchStepRequest()
                step_req.ParseFromString(message)
                if step_req.episode_id != req.episode_id:
                    raise PolicyStepError(f"Received episode_id {step_req.episode_id!r}, expected {req.episode_id!r}")
                step_resp = self._service.batch_step(step_req)
                ws.send(step_resp.SerializeToString())
        finally:
            if episode_id is not None:
                self._service.close_episode(episode_id)
            logger.info("Client disconnected, shutting down")
            self._ws_server.shutdown()


class WebSocketPolicyServerClient(MultiAgentPolicy):
    def __init__(self, policy_env_info: PolicyEnvInterface, *, url: str, agent_ids: list[int]):
        super().__init__(policy_env_info)
        self._url = url
        self._ws = ws_connect(url, open_timeout=PREPARE_TIMEOUT)
        self._episode_id = "ws-episode"
        self._next_step_id = 0
        self._ws_lock = threading.Lock()
        self._agents: dict[int, WebSocketPolicyServerAgentClient] = {}
        self._prepare(agent_ids)

    def _prepare(self, agent_ids: list[int]) -> None:
        action_names = self._policy_env_info.all_action_names
        game_rules = policy_pb2.GameRules(
            features=[
                policy_pb2.GameRules.Feature(id=f.id, name=f.name, normalization=f.normalization)
                for f in self._policy_env_info.obs_features
            ],
            actions=[policy_pb2.GameRules.Action(id=i, name=name) for i, name in enumerate(action_names)],
        )
        req = policy_pb2.PreparePolicyRequest(
            episode_id=self._episode_id,
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

    def step_agents(self, agent_observations: list[tuple[int, bytes]]) -> list[int]:
        with self._ws_lock:
            step_req = policy_pb2.BatchStepRequest(
                episode_id=self._episode_id,
                step_id=self._next_step_id,
                agent_observations=[
                    policy_pb2.AgentObservations(agent_id=agent_id, observations=obs_bytes)
                    for agent_id, obs_bytes in agent_observations
                ],
            )
            self._next_step_id += 1
            self._ws.send(step_req.SerializeToString())
            resp = self._ws.recv()

        if not isinstance(resp, bytes):
            raise PolicyStepError("Expected binary BatchStepResponse message")

        step_resp = policy_pb2.BatchStepResponse()
        step_resp.ParseFromString(resp)

        action_ids_by_agent: dict[int, int] = {}
        for agent_actions in step_resp.agent_actions:
            if len(agent_actions.action_id) != 1:
                raise PolicyStepError(f"Agent {agent_actions.agent_id} returned {len(agent_actions.action_id)} actions")
            action_ids_by_agent[agent_actions.agent_id] = agent_actions.action_id[0]

        missing_agent_ids = [agent_id for agent_id, _ in agent_observations if agent_id not in action_ids_by_agent]
        if missing_agent_ids:
            raise PolicyStepError(f"Missing actions for agent_ids {missing_agent_ids}")

        return [action_ids_by_agent[agent_id] for agent_id, _ in agent_observations]

    def step_agent(self, agent_id: int, obs_bytes: bytes) -> int:
        return self.step_agents([(agent_id, obs_bytes)])[0]

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
        try:
            return _decode_action_id(action_id, self._parent.policy_env_info)
        except PolicyStepError as e:
            raise PolicyStepError(f"{e} for agent {self._agent_id}") from e

    def can_step_group(self, policies: Sequence[AgentPolicy]) -> bool:
        return all(
            isinstance(policy, WebSocketPolicyServerAgentClient) and policy._parent is self._parent
            for policy in policies
        )

    def step_group(self, observations: list[tuple[int, AgentObservation]]) -> list[Action]:
        serialized = [(agent_id, _serialize_triplet_v1(obs)) for agent_id, obs in observations]
        try:
            action_ids = self._parent.step_agents(serialized)
        except (ConnectionClosed, EOFError, OSError) as e:
            raise PolicyStepError("WebSocket communication failed during batched step") from e

        actions: list[Action] = []
        for (agent_id, _), action_id in zip(observations, action_ids, strict=True):
            try:
                actions.append(_decode_action_id(action_id, self._parent.policy_env_info))
            except PolicyStepError as e:
                raise PolicyStepError(f"{e} for agent {agent_id}") from e
        return actions
