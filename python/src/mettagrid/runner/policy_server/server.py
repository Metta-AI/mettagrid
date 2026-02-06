import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

import typer

from mettagrid.config.id_map import ObservationFeatureSpec
from mettagrid.policy.loader import initialize_or_load_policy
from mettagrid.policy.policy import AgentPolicy, MultiAgentPolicy
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.protobuf.sim.policy_v1 import policy_pb2
from mettagrid.simulator import AgentObservation, ObservationToken
from mettagrid.util.uri_resolvers.schemes import policy_spec_from_uri

logger = logging.getLogger(__name__)

cli = typer.Typer()


class EpisodeNotFoundError(Exception):
    def __init__(self, episode_id: str):
        self.episode_id = episode_id
        super().__init__(f"unknown episode_id: {episode_id}")


class AgentNotFoundError(Exception):
    def __init__(self, agent_id: int):
        self.agent_id = agent_id
        super().__init__(f"unknown agent_id: {agent_id}")


class UnsupportedObservationFormatError(Exception):
    def __init__(self, format: int):
        self.format = format
        super().__init__(f"unsupported observation format: {format}")


def parse_triplet_v1(data: bytes, features: dict[int, ObservationFeatureSpec]) -> list[ObservationToken]:
    tokens = []
    for i in range(0, len(data), 3):
        if i + 2 >= len(data):
            break
        loc_byte, feature_id, value = data[i], data[i + 1], data[i + 2]
        if loc_byte == 0xFF:
            continue
        feature = features.get(feature_id)
        if feature is None:
            continue
        tokens.append(
            ObservationToken(
                feature=feature,
                value=value,
                raw_token=(loc_byte, feature_id, value),
            )
        )
    return tokens


ObservationParser = Callable[[bytes, dict[int, ObservationFeatureSpec]], list[ObservationToken]]

OBSERVATION_PARSERS: dict[int, ObservationParser] = {
    policy_pb2.AgentObservations.Format.TRIPLET_V1: parse_triplet_v1,
}


@dataclass
class Episode:
    episode_id: str
    policy: MultiAgentPolicy
    features: dict[int, ObservationFeatureSpec]
    actions: dict[str, int]
    parse_observations: ObservationParser
    agent_policies: dict[int, AgentPolicy]


EnvInterfaceAdapter = Callable[[policy_pb2.PreparePolicyRequest], PolicyEnvInterface]


class LocalPolicyServer:
    def __init__(
        self,
        policy_factory: Callable[[PolicyEnvInterface], MultiAgentPolicy],
        env_interface_adapter: EnvInterfaceAdapter,
    ):
        self._policy_factory = policy_factory
        self._env_interface_adapter = env_interface_adapter
        self._episodes: dict[str, Episode] = {}

    def prepare_policy(self, req: policy_pb2.PreparePolicyRequest) -> policy_pb2.PreparePolicyResponse:
        logger.info("PreparePolicy: %s", req)
        parse_observations = OBSERVATION_PARSERS.get(req.observations_format)
        if parse_observations is None:
            raise UnsupportedObservationFormatError(req.observations_format)
        policy_env = self._env_interface_adapter(req)
        policy = self._policy_factory(policy_env)
        features = {
            f.id: ObservationFeatureSpec(id=f.id, name=f.name, normalization=f.normalization)
            for f in req.game_rules.features
        }
        actions = {a.name: a.id for a in req.game_rules.actions}
        agent_policies = {agent_id: policy.agent_policy(agent_id) for agent_id in req.agent_ids}
        episode = Episode(
            episode_id=req.episode_id,
            policy=policy,
            features=features,
            actions=actions,
            parse_observations=parse_observations,
            agent_policies=agent_policies,
        )
        self._episodes[req.episode_id] = episode
        return policy_pb2.PreparePolicyResponse()

    def batch_step(self, req: policy_pb2.BatchStepRequest) -> policy_pb2.BatchStepResponse:
        logger.debug("BatchStep: %s", req)
        episode = self._episodes.get(req.episode_id)
        if episode is None:
            raise EpisodeNotFoundError(req.episode_id)

        resp = policy_pb2.BatchStepResponse()
        for agent_obs in req.agent_observations:
            agent_id = agent_obs.agent_id
            agent_policy = episode.agent_policies.get(agent_id)
            if agent_policy is None:
                raise AgentNotFoundError(agent_id)
            tokens = episode.parse_observations(agent_obs.observations, episode.features)
            observation = AgentObservation(agent_id=agent_id, tokens=tokens)
            action = agent_policy.step(observation)
            action_id = episode.actions.get(action.name)
            actions: list[int] = []
            if action_id is None:
                logger.warning("episode %r agent %d returned unknown action %r", req.episode_id, agent_id, action.name)
            else:
                actions.append(action_id)
            resp.agent_actions.append(policy_pb2.AgentActions(agent_id=agent_id, action_id=actions))
        return resp


@cli.command()
def main(
    policy: Annotated[str, typer.Option(help="Policy ID")],
    socket_path: Annotated[str, typer.Option(help="Unix socket path")],
    ready_file: Annotated[str | None, typer.Option(help="Write 'ready' when listening")] = None,
):
    """Serve a policy over a Unix domain socket using a binary protocol."""
    from mettagrid.runner.policy_server.socket_transport import SocketPolicyServer  # noqa: PLC0415

    policy_spec = policy_spec_from_uri(policy)

    def policy_factory(env: PolicyEnvInterface) -> MultiAgentPolicy:
        return initialize_or_load_policy(env, policy_spec, device_override="cpu")

    service = LocalPolicyServer(policy_factory, lambda req: PolicyEnvInterface.from_proto(req.env_interface))
    SocketPolicyServer(service, socket_path, ready_file).serve()


if __name__ == "__main__":
    cli()
