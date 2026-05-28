from typing import Literal

from pydantic import BaseModel, Field, model_validator

from mettagrid.config.any_env_config import AnyEnvConfig
from mettagrid.types import EpisodeStats
from mettagrid.util.uri_resolvers.schemes import parse_uri


class PureSingleEpisodeJob(BaseModel):
    policy_uris: list[str]
    policy_names: list[str] | None = None

    # It is important that this is explicit, else the results will have to include the choices we made
    # when randomizing
    assignments: list[int]

    env: AnyEnvConfig

    results_uri: str | None  # file:// URI for episode results JSON
    replay_uri: str | None  # file:// URI for replay. If missing, do not generate a replay
    debug_dir: str | None = None  # Directory for observability outputs (trace.json, etc.)

    # There's no way to ask us to generate a seed; the caller has to pick one
    seed: int = 0

    max_action_time_ms: int = 10000
    overage_budget_ms: int | None = None
    episode_tags: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_output_uris(self) -> "PureSingleEpisodeJob":
        if self.policy_names is not None and len(self.policy_names) != len(self.policy_uris):
            raise ValueError("policy_names must have the same length as policy_uris")

        for uri in (self.replay_uri, self.results_uri):
            if uri is None:
                continue
            parsed = parse_uri(uri, allow_none=False)
            if parsed.scheme != "file" or not parsed.local_path.parent.exists():
                raise ValueError(f"URI {uri} must be a file:// URI with an existing parent directory")

        if self.replay_uri is not None and not self.replay_uri.endswith((".json.z", ".json.gz")):
            raise ValueError("Replay URI must end with .json.z or .json.gz")

        if len(self.assignments) != self.env.num_agents or not all(
            0 <= a < len(self.policy_uris) for a in self.assignments
        ):
            raise ValueError("Assignments must match agent count and be within policy range")

        return self


class PureSingleEpisodeResult(BaseModel):
    rewards: list[float]
    action_timeouts: list[int]
    stats: EpisodeStats
    steps: int
    time_averaged_game_stats: dict[str, float] = Field(default_factory=dict)
    # One entry per agent: the step at which overage budget was exhausted, or None if never exceeded.
    overage_exceeded_at: list[int | None]


RunnerErrorType = Literal["config_error", "policy_error", "crash", "unknown"]


class RunnerError(BaseModel):
    """Structured error written by the runner to S3 on failure."""

    error_type: RunnerErrorType
    message: str

    # Policy-failure attribution: set when error_type == "policy_error" and
    # the failing policy could be identified.
    failed_policy_index: int | None = None
    failed_policy_uri: str | None = None
    failed_policy_name: str | None = None
