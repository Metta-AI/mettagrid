from pydantic import BaseModel, Field, model_validator

from mettagrid import MettaGridConfig
from mettagrid.types import EpisodeStats
from mettagrid.util.uri_resolvers.schemes import parse_uri


class EpisodeSpec(BaseModel):
    policy_uris: list[str]
    assignments: list[int]
    env: MettaGridConfig
    seed: int = 0
    max_action_time_ms: int = 10000


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
            parsed = parse_uri(uri, allow_none=False)
            if parsed.scheme != "file" or not parsed.local_path.parent.exists():
                raise ValueError(f"URI {uri} must be a file:// URI with an existing parent directory")

        if self.replay_uri is not None and not self.replay_uri.endswith((".json.z", ".json.gz")):
            raise ValueError("Replay URI must end with .json.z or .json.gz")

        if len(self.assignments) != self.env.game.num_agents or not all(
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


class RuntimeInfo(BaseModel):
    git_commit: str | None = None
    instance_type: str | None = None


class SingleEpisodeJob(EpisodeSpec):
    model_config = {"extra": "ignore"}

    episode_tags: dict[str, str] = Field(default_factory=dict)

    def episode_spec(self) -> EpisodeSpec:
        return EpisodeSpec(
            policy_uris=self.policy_uris,
            assignments=self.assignments,
            env=self.env,
            seed=self.seed,
            max_action_time_ms=self.max_action_time_ms,
        )
