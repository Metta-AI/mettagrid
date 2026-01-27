"""Observation configuration.

Feature IDs and names are managed by IdMap.
Changing feature IDs will break models trained on old feature IDs.
"""

from enum import Enum

from pydantic import ConfigDict, Field

from mettagrid.base_config import Config


class StatsSource(Enum):
    """Source of stats for observation."""

    OWN = "own"  # Agent's personal stats
    GLOBAL = "global"  # Game-level stats from StatsTracker
    COLLECTIVE = "collective"  # Agent's collective stats


class StatsValue(Config):
    """Configuration for a stat value to observe."""

    name: str  # Stat key, e.g. "carbon.gained"
    source: StatsSource = StatsSource.OWN
    delta: bool = False  # True = per-step change, False = cumulative


class GlobalObsConfig(Config):
    """Global observation configuration."""

    episode_completion_pct: bool = Field(default=True)

    # Controls whether the last_action global token is included
    last_action: bool = Field(default=True)

    last_reward: bool = Field(default=True)

    # Compass token that points toward the assembler/hub center
    compass: bool = Field(default=False)

    # Goal tokens that indicate rewarding resources
    goal_obs: bool = Field(default=False)

    # Stats to include as observations
    stats_obs: list[StatsValue] = Field(default_factory=list)


class ObsConfig(Config):
    """Observation configuration."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    width: int = Field(default=11)
    height: int = Field(default=11)
    token_dim: int = Field(default=3)
    num_tokens: int = Field(default=200)
    token_value_base: int = Field(default=256)
    """Base for multi-token inventory encoding (value per token: 0 to base-1).

    Default 256 for efficient byte packing.
    """
    global_obs: GlobalObsConfig = Field(default_factory=GlobalObsConfig)
