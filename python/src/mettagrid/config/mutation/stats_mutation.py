"""Stats mutation configuration and helper functions."""

from __future__ import annotations

from enum import StrEnum, auto
from typing import Literal

from pydantic import Field

from mettagrid.config.mutation.mutation import Mutation


class StatsTarget(StrEnum):
    """Target for stats logging - which stats tracker to log to."""

    GAME = auto()  # log to game-level stats tracker
    AGENT = auto()  # log to target agent's stats tracker
    COLLECTIVE = auto()  # log to target's collective's stats tracker


class StatsMutation(Mutation):
    """Log a stat with a specified delta.

    This mutation records a stat value that can be tracked in metrics.
    Useful for events to track when they fire or record custom metrics.

    The target field specifies which stats tracker to log to:
    - GAME: global game-level stats (accessible via game stats API)
    - AGENT: the target agent's individual stats tracker
    - COLLECTIVE: the target's collective's stats tracker
    """

    mutation_type: Literal["stats"] = "stats"
    stat: str = Field(description="Name of the stat to log")
    delta: int = Field(default=1, description="Delta to add to the stat")
    target: StatsTarget = Field(
        default=StatsTarget.COLLECTIVE,
        description="Which stats tracker to log to (game, agent, or collective)",
    )


# ===== Helper Mutation Functions =====


def logStat(stat: str, delta: int = 1, target: StatsTarget = StatsTarget.COLLECTIVE) -> StatsMutation:
    """Mutation: log a stat with a specified delta.

    Args:
        stat: Name of the stat to log.
        delta: Delta to add to the stat (default 1).
        target: Which stats tracker to log to (game, agent, or collective). Defaults to COLLECTIVE.
    """
    return StatsMutation(stat=stat, delta=delta, target=target)
