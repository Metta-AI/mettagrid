import json
import logging
import sys
from typing import Sequence

from pydantic import BaseModel, Field, model_validator

from mettagrid import MettaGridConfig
from mettagrid.types import EpisodeStats
from mettagrid.util.uri_resolvers.schemes import parse_uri

logger = logging.getLogger(__name__)


def _validate_output_uri(uri: str) -> None:
    parsed = parse_uri(uri, allow_none=False)
    if parsed.scheme != "file" or not parsed.local_path.parent.exists():
        raise ValueError(f"URI {uri} must be a file:// URI with an existing parent directory")


def _validate_assignments(assignments: Sequence[int], num_agents: int, num_policies: int) -> None:
    if len(assignments) != num_agents or not all(0 <= assignment < num_policies for assignment in assignments):
        raise ValueError("Assignments must match agent count and be within policy range")


class PureSingleEpisodeJob(BaseModel):
    policy_uris: list[str]

    # It is important that this is explicit, else the results will have to include the choices we made
    # when randomizing
    assignments: list[int]

    env: MettaGridConfig

    results_uri: str | None  # file:// URI for episode results JSON
    replay_uri: str | None  # file:// URI for replay. If missing, do not generate a replay
    debug_dir: str | None = None  # Directory for observability outputs (trace.json, etc.)

    # There's no way to ask us to generate a seed; the caller has to pick one
    seed: int = 0

    max_action_time_ms: int = 10000
    episode_tags: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_output_uris(self) -> "PureSingleEpisodeJob":
        for uri in (self.replay_uri, self.results_uri):
            if uri is None:
                continue
            _validate_output_uri(uri)

        if self.replay_uri is not None and not self.replay_uri.endswith((".json.z", ".json.gz")):
            raise ValueError("Replay URI must end with .json.z or .json.gz")

        _validate_assignments(self.assignments, self.env.game.num_agents, len(self.policy_uris))

        return self


class PureSingleEpisodeResult(BaseModel):
    rewards: list[float]
    action_timeouts: list[int]
    stats: EpisodeStats
    steps: int


if __name__ == "__main__":
    from mettagrid.runner.rollout import run_sandboxed_episode

    logging.getLogger("httpx").setLevel(logging.WARNING)

    with open(sys.argv[1]) as f:
        args = json.load(f)
    job = PureSingleEpisodeJob.model_validate(args["job"])
    run_sandboxed_episode(job)
