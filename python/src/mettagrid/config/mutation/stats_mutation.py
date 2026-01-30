"""Stats mutation configuration and helper functions."""

from __future__ import annotations

from enum import StrEnum, auto
from typing import Literal

from pydantic import Field

from mettagrid.config.mutation.mutation import Mutation


class StatsTarget(StrEnum):
    """Target for stats logging - which stats tracker to log to."""

    GAME = auto()  # log to game-level stats tracker
    AGENT = auto()  # log to entity's (actor or target) agent stats tracker
    COLLECTIVE = auto()  # log to entity's (actor or target) collective's stats tracker


class StatsEntity(StrEnum):
    """Which entity to use for resolving the stats tracker."""

    TARGET = auto()  # use the target entity
    ACTOR = auto()  # use the actor entity


class StatsMutation(Mutation):
    """Log a stat with a specified delta.

    This mutation records a stat value that can be tracked in metrics.
    Useful for events to track when they fire or record custom metrics.

    The target field specifies which stats tracker to log to:
    - GAME: global game-level stats (accessible via game stats API)
    - AGENT: an agent's individual stats tracker
    - COLLECTIVE: an entity's collective's stats tracker

    The entity field specifies which entity to use when resolving AGENT or COLLECTIVE:
    - TARGET: use the target entity (default)
    - ACTOR: use the actor entity
    """

    mutation_type: Literal["stats"] = "stats"
    stat: str = Field(description="Name of the stat to log")
    delta: int = Field(default=1, description="Delta to add to the stat")
    target: StatsTarget = Field(
        default=StatsTarget.COLLECTIVE,
        description="Which stats tracker to log to (game, agent, or collective)",
    )
    entity: StatsEntity = Field(
        default=StatsEntity.TARGET,
        description="Which entity to use for resolving AGENT or COLLECTIVE target (target or actor)",
    )


# ===== Helper Mutation Functions =====


def logStat(
    stat: str,
    delta: int = 1,
    target: StatsTarget = StatsTarget.COLLECTIVE,
    entity: StatsEntity = StatsEntity.TARGET,
) -> StatsMutation:
    """Mutation: log a stat with a specified delta.

    Args:
        stat: Name of the stat to log.
        delta: Delta to add to the stat (default 1).
        target: Which stats tracker to log to (game, agent, or collective). Defaults to COLLECTIVE.
        entity: Which entity to use for resolving AGENT or COLLECTIVE target. Defaults to TARGET.
    """
    return StatsMutation(stat=stat, delta=delta, target=target, entity=entity)


def logStatToGame(stat: str, delta: int = 1) -> StatsMutation:
    """Mutation: log a stat to the game-level stats tracker.

    Args:
        stat: Name of the stat to log.
        delta: Delta to add to the stat (default 1).
    """
    return StatsMutation(stat=stat, delta=delta, target=StatsTarget.GAME)


def logTargetAgentStat(stat: str, delta: int = 1) -> StatsMutation:
    """Mutation: log a stat to the target agent's stats tracker.

    Args:
        stat: Name of the stat to log.
        delta: Delta to add to the stat (default 1).
    """
    return StatsMutation(stat=stat, delta=delta, target=StatsTarget.AGENT, entity=StatsEntity.TARGET)


def logActorAgentStat(stat: str, delta: int = 1) -> StatsMutation:
    """Mutation: log a stat to the actor agent's stats tracker.

    Args:
        stat: Name of the stat to log.
        delta: Delta to add to the stat (default 1).
    """
    return StatsMutation(stat=stat, delta=delta, target=StatsTarget.AGENT, entity=StatsEntity.ACTOR)


def logTargetCollectiveStat(stat: str, delta: int = 1) -> StatsMutation:
    """Mutation: log a stat to the target's collective's stats tracker.

    Args:
        stat: Name of the stat to log.
        delta: Delta to add to the stat (default 1).
    """
    return StatsMutation(stat=stat, delta=delta, target=StatsTarget.COLLECTIVE, entity=StatsEntity.TARGET)


def logActorCollectiveStat(stat: str, delta: int = 1) -> StatsMutation:
    """Mutation: log a stat to the actor's collective's stats tracker.

    Args:
        stat: Name of the stat to log.
        delta: Delta to add to the stat (default 1).
    """
    return StatsMutation(stat=stat, delta=delta, target=StatsTarget.COLLECTIVE, entity=StatsEntity.ACTOR)
