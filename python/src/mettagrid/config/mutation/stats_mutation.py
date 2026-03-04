"""Stats mutation configuration and helper functions."""

from __future__ import annotations

from enum import auto
from typing import Literal, Optional

from pydantic import Field

from mettagrid.base_config import ConfigStrEnum
from mettagrid.config.game_value import AnyGameValue, SumGameValue, stat, val
from mettagrid.config.mutation.mutation import Mutation


class StatsTarget(ConfigStrEnum):
    """Target for stats logging - which stats tracker to log to."""

    GAME = auto()  # log to game-level stats tracker
    AGENT = auto()  # log to entity's (actor or target) agent stats tracker


class StatsEntity(ConfigStrEnum):
    """Which entity to use for resolving the stats tracker."""

    TARGET = auto()  # use the target entity
    ACTOR = auto()  # use the actor entity


class StatsMutation(Mutation):
    """Set a stat to a computed value.

    The source game value expression is resolved and written (set) to the stat.
    Accumulation (add) semantics are expressed via a self-referencing SumGameValue
    in the source, e.g. source=SumGameValue(values=[stat("game.hits"), val(1)])
    means hits = hits + 1.

    The target field specifies which stats tracker to write to:
    - GAME: global game-level stats (accessible via game stats API)
    - AGENT: an agent's individual stats tracker

    The entity field specifies which entity to use when resolving AGENT:
    - TARGET: use the target entity (default)
    - ACTOR: use the actor entity
    """

    mutation_type: Literal["stats"] = "stats"
    stat: str = Field(description="Name of the stat to set")
    target: StatsTarget = Field(
        default=StatsTarget.GAME,
        description="Which stats tracker to write to (game or agent)",
    )
    entity: StatsEntity = Field(
        default=StatsEntity.TARGET,
        description="Which entity to use for resolving AGENT target (target or actor)",
    )
    source: AnyGameValue = Field(description="Game value expression to compute the new stat value")


# ===== Helper Mutation Functions =====


def _accumulate(stat_name: str, effective_value: AnyGameValue, target: StatsTarget) -> SumGameValue:
    """Wrap a value in SumGameValue for accumulation: new = old + value."""
    scope_prefix = "game." if target == StatsTarget.GAME else ""
    self_ref = stat(f"{scope_prefix}{stat_name}")
    return SumGameValue(values=[self_ref, effective_value])


def logStat(
    stat: str,
    delta: float = 1,
    target: StatsTarget = StatsTarget.GAME,
    entity: StatsEntity = StatsEntity.TARGET,
    source: Optional[AnyGameValue] = None,
) -> StatsMutation:
    """Mutation: accumulate a stat (new = old + delta_or_source).

    Args:
        stat: Name of the stat to accumulate.
        delta: Value to add to the stat (default 1). Ignored when source is provided.
        target: Which stats tracker to log to (game or agent). Defaults to GAME.
        entity: Which entity to use for resolving AGENT target. Defaults to TARGET.
        source: Dynamic source for the added value. When provided, delta is ignored.
    """
    effective_value = source if source is not None else val(delta)
    return StatsMutation(stat=stat, target=target, entity=entity, source=_accumulate(stat, effective_value, target))


def logStatToGame(stat: str, delta: float = 1, source: Optional[AnyGameValue] = None) -> StatsMutation:
    """Mutation: accumulate a stat in the game-level stats tracker.

    Args:
        stat: Name of the stat to accumulate.
        delta: Value to add to the stat (default 1). Ignored when source is provided.
        source: Dynamic source for the added value.
    """
    effective_value = source if source is not None else val(delta)
    return StatsMutation(
        stat=stat, target=StatsTarget.GAME, source=_accumulate(stat, effective_value, StatsTarget.GAME)
    )


def logTargetAgentStat(stat: str, delta: float = 1, source: Optional[AnyGameValue] = None) -> StatsMutation:
    """Mutation: accumulate a stat in the target agent's stats tracker.

    Args:
        stat: Name of the stat to accumulate.
        delta: Value to add to the stat (default 1). Ignored when source is provided.
        source: Dynamic source for the added value.
    """
    effective_value = source if source is not None else val(delta)
    return StatsMutation(
        stat=stat,
        target=StatsTarget.AGENT,
        entity=StatsEntity.TARGET,
        source=_accumulate(stat, effective_value, StatsTarget.AGENT),
    )


def logActorAgentStat(stat: str, delta: float = 1, source: Optional[AnyGameValue] = None) -> StatsMutation:
    """Mutation: accumulate a stat in the actor agent's stats tracker.

    Args:
        stat: Name of the stat to accumulate.
        delta: Value to add to the stat (default 1). Ignored when source is provided.
        source: Dynamic source for the added value.
    """
    effective_value = source if source is not None else val(delta)
    return StatsMutation(
        stat=stat,
        target=StatsTarget.AGENT,
        entity=StatsEntity.ACTOR,
        source=_accumulate(stat, effective_value, StatsTarget.AGENT),
    )
