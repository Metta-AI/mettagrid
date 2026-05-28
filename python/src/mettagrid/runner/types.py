from typing import Literal

from pydantic import BaseModel, Field

from mettagrid.types import EpisodeStats


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
