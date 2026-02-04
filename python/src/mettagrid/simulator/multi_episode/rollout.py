"""Shared rollout result models."""

from __future__ import annotations

from pydantic import BaseModel

from mettagrid.types import EpisodeStats


class EpisodeRolloutResult(BaseModel):
    assignments: list[int]
    rewards: list[float]
    action_timeouts: list[int]
    stats: EpisodeStats
    replay_path: str | None
    steps: int
    max_steps: int


class MultiEpisodeRolloutResult(BaseModel):
    episodes: list[EpisodeRolloutResult]
