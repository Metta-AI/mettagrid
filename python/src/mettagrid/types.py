"""Core types for MettaGrid that need to be importable without circular dependencies.

These types are intentionally kept in a minimal module with no internal dependencies
to avoid circular import issues.
"""

from dataclasses import dataclass
from typing import NotRequired, TypedDict


@dataclass
class Action:
    """Represents an action that can be taken by an agent."""

    name: str


# Re-export EpisodeStats from C++ bindings for convenience
# Using TypedDict definition to avoid importing from mettagrid_c at module level
# which can cause issues during installation when the C++ module isn't built yet
StatsDict = dict[str, float]


class EpisodeStats(TypedDict):
    """Episode statistics returned by the C++ simulator."""

    game: StatsDict
    agent: list[StatsDict]
    collective: NotRequired[dict[str, StatsDict]]
