from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from mettagrid.config.any_env_config import AnyEnvConfig
from mettagrid.types import EpisodeStats
from mettagrid.util.uri_resolvers.schemes import parse_uri


def _migrate_game_engine_into_env(data: Any) -> Any:
    """Move top-level ``game_engine`` into ``env`` for backward compat.

    Old serialized job dicts have ``game_engine`` as a sibling of ``env``.
    The new schema stores it inside the env config so the discriminated union
    can pick the right type.

    For BitWorld, old jobs used a MettaGridConfig carrier with game params
    stuffed into ``env.game``.  We translate those carrier fields into
    ``BitWorldEnvConfig`` fields and strip the MettaGrid scaffolding.
    """
    if isinstance(data, dict) and "env" in data and isinstance(data["env"], dict):
        env = data["env"]
        if "game_engine" not in env and "game_engine" in data:
            env["game_engine"] = data.pop("game_engine")

        if env.get("game_engine") == "bitworld" and "game" in env:
            game = env.pop("game")
            env.setdefault("max_ticks", game.get("max_steps", 10000))
            env.setdefault("num_players", game.get("num_agents", 5))
            # Strip remaining MettaGrid carrier fields
            for key in ("desync_episodes", "map_builder"):
                env.pop(key, None)

    return data


class EpisodeJobSummary(BaseModel):
    """Minimal job fields needed to record an episode in observatory.

    extra="ignore" ensures runner schema changes never break recording.
    SingleEpisodeJob extends this (via EpisodeSpec) so the fields can't diverge.
    """

    model_config = {"extra": "ignore"}

    policy_uris: list[str]
    assignments: list[int]
    policy_names: list[str] | None = None
    episode_tags: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_policy_names(self) -> "EpisodeJobSummary":
        if self.policy_names is not None and len(self.policy_names) != len(self.policy_uris):
            raise ValueError("policy_names must have the same length as policy_uris")
        return self


class EpisodeSpec(EpisodeJobSummary):
    env: AnyEnvConfig
    seed: int = 0
    max_action_time_ms: int = 10000
    overage_budget_ms: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _migrate_game_engine(cls, data: Any) -> Any:
        return _migrate_game_engine_into_env(data)


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

    @model_validator(mode="before")
    @classmethod
    def _migrate_game_engine(cls, data: Any) -> Any:
        return _migrate_game_engine_into_env(data)

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
    # None for results produced before overage tracking existed (e.g. old S3 artifacts).
    # When present, one entry per agent: the step at which overage budget was exhausted, or None if never exceeded.
    overage_exceeded_at: list[int | None] | None = None


class RuntimeInfo(BaseModel):
    git_commit: str | None = None
    cogames_version: str | None = None
    instance_type: str | None = None


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


class SingleEpisodeJob(EpisodeSpec):
    model_config = {"extra": "ignore"}

    def episode_spec(self) -> EpisodeSpec:
        return EpisodeSpec(
            policy_uris=self.policy_uris,
            policy_names=self.policy_names,
            assignments=self.assignments,
            env=self.env,
            seed=self.seed,
            max_action_time_ms=self.max_action_time_ms,
            overage_budget_ms=self.overage_budget_ms,
        )
