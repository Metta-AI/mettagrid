"""Game value types for rewards and observations.

GameValue is the base class for values queryable from game state.
Used for rewards (numerators/denominators) and observations.
"""

from enum import Enum
from typing import Union

from pydantic import field_serializer

from mettagrid.base_config import Config


class StatsSource(Enum):
    """Source of stats for observation."""

    OWN = "own"  # Agent's personal stats
    GLOBAL = "global"  # Game-level stats from StatsTracker
    COLLECTIVE = "collective"  # Agent's collective stats


class GameValue(Config):
    """Base class for values queryable from game state."""

    pass


class StatsValue(GameValue):
    """Stat value from agent, collective, or global tracker."""

    name: str  # Stat key, e.g. "carbon.gained"
    source: StatsSource = StatsSource.OWN
    delta: bool = False  # True = per-step change, False = cumulative

    @field_serializer("source")
    def serialize_source(self, value: StatsSource) -> str:
        return value.value


class Inventory(GameValue):
    """Agent's own inventory item count."""

    item: str


class CollectiveInventory(GameValue):
    """Agent's collective inventory item count."""

    item: str


class NumObjects(GameValue):
    """Count of objects by type.

    Shorthand for NumTaggedObjects with the type tag.
    E.g., NumObjects("junction") counts objects with tag "type:junction".
    """

    object_type: str  # e.g., "junction"


class NumTaggedObjects(GameValue):
    """Count of objects with an arbitrary tag.

    E.g., NumTaggedObjects("vibe:aligned") counts all aligned objects.
    """

    tag: str  # e.g., "type:junction", "vibe:aligned", "collective:cogs"


# Union type for all GameValue types (useful for type hints)
AnyGameValue = Union[StatsValue, Inventory, CollectiveInventory, NumObjects, NumTaggedObjects]
