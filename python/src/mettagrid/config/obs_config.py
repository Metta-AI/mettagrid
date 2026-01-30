"""Observation configuration.

Feature IDs and names are managed by IdMap.
Changing feature IDs will break models trained on old feature IDs.
"""

from collections.abc import Sequence

from pydantic import ConfigDict, Field

from mettagrid.base_config import Config
from mettagrid.config.game_value import AnyGameValue


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

    # Local position: offset from spawn as directional tokens (lp:east, lp:west, lp:north, lp:south)
    local_position: bool = Field(default=False)

    # Game values to include as observations
    obs: Sequence[AnyGameValue] = Field(default_factory=list)


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
