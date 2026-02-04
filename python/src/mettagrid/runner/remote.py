import logging
import uuid

import httpx
from google.protobuf import json_format

from mettagrid.policy.policy import AgentPolicy, MultiAgentPolicy
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.protobuf.sim.policy_v1 import policy_pb2
from mettagrid.simulator import Action, AgentObservation

logger = logging.getLogger(__name__)


class PolicyStepError(Exception):
    pass


_PREPARE_PATH = "/mettagrid.protobuf.sim.policy_v1.Policy/PreparePolicy"
_BATCH_STEP_PATH = "/mettagrid.protobuf.sim.policy_v1.Policy/BatchStep"


def _serialize_triplet_v1(obs: AgentObservation) -> bytes:
    buf = bytearray()
    for token in obs.tokens:
        loc_byte, feature_id, value = token.raw_token
        buf.extend((loc_byte, feature_id, value))
    return bytes(buf)


class RemoteAgentPolicy(AgentPolicy):
    def __init__(self, parent: "RemoteMultiAgentPolicy", agent_id: int):
        super().__init__(parent.policy_env_info)
        self._parent = parent
        self._agent_id = agent_id

    def step(self, obs: AgentObservation) -> Action:
        obs_bytes = _serialize_triplet_v1(obs)
        req = policy_pb2.BatchStepRequest(
            episode_id=self._parent._episode_id,
            step_id=0,
            agent_observations=[
                policy_pb2.AgentObservations(agent_id=self._agent_id, observations=obs_bytes),
            ],
        )

        try:
            resp = self._parent._client.post(
                f"{self._parent._base_url}{_BATCH_STEP_PATH}",
                json=json_format.MessageToDict(req),
                timeout=self._parent._request_timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise PolicyStepError(f"Policy server returned {e.response.status_code} for agent {self._agent_id}") from e
        except httpx.HTTPError as e:
            raise PolicyStepError(f"Policy server request failed for agent {self._agent_id}: {e}") from e

        batch_resp = json_format.ParseDict(resp.json(), policy_pb2.BatchStepResponse())
        if not batch_resp.agent_actions:
            return Action(name="noop")

        action_ids = batch_resp.agent_actions[0].action_id
        if not action_ids:
            return Action(name="noop")

        action_id = action_ids[0]
        action_names = self._parent.policy_env_info.action_names
        if 0 <= action_id < len(action_names):
            return Action(name=action_names[action_id])
        return Action(name="noop")


class RemoteMultiAgentPolicy(MultiAgentPolicy):
    def __init__(
        self,
        policy_env_info: PolicyEnvInterface,
        *,
        base_url: str,
        episode_id: str | None = None,
        request_timeout: float = 30.0,
    ):
        super().__init__(policy_env_info)
        self._base_url = base_url.rstrip("/")
        self._request_timeout = request_timeout
        self._episode_id = episode_id or str(uuid.uuid4())
        self._agents: dict[int, RemoteAgentPolicy] = {}
        self._client = httpx.Client()
        self._prepare(list(range(policy_env_info.num_agents)))

    def agent_policy(self, agent_id: int) -> AgentPolicy:
        if agent_id not in self._agents:
            self._agents[agent_id] = RemoteAgentPolicy(self, agent_id)
        return self._agents[agent_id]

    def reset(self) -> None:
        self._agents.clear()
        self._episode_id = str(uuid.uuid4())
        self._prepare(list(range(self._policy_env_info.num_agents)))

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "RemoteMultiAgentPolicy":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

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
            episode_id=self._episode_id,
            game_rules=game_rules,
            agent_ids=agent_ids,
            observations_format=policy_pb2.AgentObservations.Format.TRIPLET_V1,
        )
        resp = self._client.post(
            f"{self._base_url}{_PREPARE_PATH}",
            json=json_format.MessageToDict(req),
            timeout=self._request_timeout,
        )
        resp.raise_for_status()
