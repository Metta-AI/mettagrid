"""Territory configuration: game-level territory types and object-level territory controls."""

from __future__ import annotations

from pydantic import Field

from mettagrid.base_config import Config
from mettagrid.config.handler_config import Handler


class TerritoryConfig(Config):
    """Game-level definition of a territory type.

    Each territory type has a tag_prefix that determines which tags compete.
    Objects with a matching tag and a TerritoryControlConfig for this territory
    project influence onto nearby cells. The tag with the highest aggregate
    strength at each cell wins.

    Handlers fire with actor = proxy cell object (carrying the winning tag),
    target = affected agent. Use filters (e.g. sharedTagPrefix("team:")) to
    distinguish friendly vs enemy territory in handler logic.

    Observation mask (per tile relative to observer):
      0 = no influence or tie
      1 = observer shares the winning tag
      2 = observer does not share the winning tag
    """

    tag_prefix: str = Field(
        description="Tag prefix for team membership (e.g. 'team:'). Objects compete via tags matching this prefix.",
    )
    on_enter: dict[str, Handler] = Field(
        default_factory=dict, description="Handlers fired once when agent enters owned territory"
    )
    on_exit: dict[str, Handler] = Field(
        default_factory=dict, description="Handlers fired once when agent leaves owned territory"
    )
    presence: dict[str, Handler] = Field(
        default_factory=dict, description="Handlers fired every tick while agent is in owned territory"
    )


class TerritoryControlConfig(Config):
    """Per-object configuration for influencing a territory type.

    The object must have a tag matching the territory's tag_prefix to
    participate. Influence at distance d = max(0, strength - decay * d).
    Effective radius is strength / decay.
    """

    territory: str = Field(description="Key into GameConfig.territories")
    strength: int = Field(default=1, ge=1, description="Base influence at distance 0")
    decay: int = Field(default=1, ge=1, description="Strength lost per unit of Euclidean distance")
