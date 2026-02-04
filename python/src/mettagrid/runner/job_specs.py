from typing import Optional

from pydantic import BaseModel, Field

from mettagrid import MettaGridConfig


class RuntimeInfo(BaseModel):
    git_commit: str | None = None
    instance_type: str | None = None


class SingleEpisodeJob(BaseModel):
    policy_uris: list[str]
    assignments: list[int]
    env: MettaGridConfig
    results_uri: Optional[str] = None
    replay_uri: Optional[str] = None
    debug_uri: Optional[str] = None
    seed: int = 0
    max_action_time_ms: int = 10000
    episode_tags: dict[str, str] = Field(default_factory=dict)
