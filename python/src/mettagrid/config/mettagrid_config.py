from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import (
    ConfigDict,
    Field,
    model_validator,
)

from mettagrid.base_config import Config
from mettagrid.config.action_config import (  # noqa: F401 - re-exported for backward compat
    ActionConfig,
    ActionsConfig,
    AttackActionConfig,
    AttackOutcome,
    CardinalDirection,
    CardinalDirections,
    ChangeVibeActionConfig,
    Direction,
    Directions,
    MoveActionConfig,
    NoopActionConfig,
    TransferActionConfig,
    VibeTransfer,
)
from mettagrid.config.event_config import EventConfig
from mettagrid.config.game_value import (  # noqa: F401 - re-exported
    AnyGameValue,
    GameValue,
    InventoryValue,
    NumObjectsValue,
    Scope,
    StatValue,
    TagCountValue,
)
from mettagrid.config.handler_config import (
    AOEConfig,
    Handler,
)
from mettagrid.config.id_map import IdMap
from mettagrid.config.obs_config import (  # noqa: F401 - re-exported
    GlobalObsConfig,
    ObsConfig,
)
from mettagrid.config.reward_config import AgentReward
from mettagrid.config.tag import Tag
from mettagrid.map_builder.ascii import AsciiMapBuilder
from mettagrid.map_builder.map_builder import AnyMapBuilderConfig
from mettagrid.map_builder.random_map import RandomMapBuilder

# ===== Python Configuration Models =====


class ResourceLimitsConfig(Config):
    """Resource limits configuration.

    Supports dynamic limits via modifiers. The effective limit is:
    min(max, max(min, sum(modifier_bonus * quantity_held)))

    Example:
        ResourceLimitsConfig(
            resources=["battery"],
            min=0,  # base limit is 0
            max=100,  # cap at 100 even with modifiers
            modifiers={"gear": 10}  # each gear adds +10 battery capacity
        )
    """

    min: int = Field(default=0, description="Minimum limit (floor for effective limit)")
    max: int = Field(default=65535, description="Maximum limit (cap for effective limit)")
    resources: list[str]
    modifiers: dict[str, int] = Field(
        default_factory=dict,
        description="Modifiers that increase the limit. Maps item name to bonus per item held.",
    )


class InventoryConfig(Config):
    """Inventory configuration for agents and chests."""

    default_limit: int = Field(default=65535, ge=0, description="Default resource limit")
    limits: dict[str, ResourceLimitsConfig] = Field(
        default_factory=dict,
        description="Resource-specific limits",
    )
    initial: dict[str, int] = Field(default_factory=dict, description="Initial inventory")

    def get_limit(self, resource_name: str) -> int:
        """Get the base resource limit for a given resource name (without modifiers)."""
        for limit_config in self.limits.values():
            if resource_name in limit_config.resources:
                return limit_config.min
        return self.default_limit


class GridObjectConfig(Config):
    """Base configuration for all grid objects.

    Python uses only names. Numeric type_ids are an internal C++ detail and are
    computed during Python→C++ conversion; they are never part of Python config
    or observations.

    Handlers:
      - on_use_handlers: Triggered when agent uses/activates this object
      - aoes: Area of effect configurations for objects that emit effects
    """

    name: str = Field(description="Canonical type_name (human-readable)")
    map_name: str = Field(default="", description="Stable key used by maps to select this config")
    render_name: str = Field(default="", description="Stable display-class identifier for theming")
    render_symbol: str = Field(default="❓", description="Symbol used for rendering (e.g., emoji)")
    tags: list[Tag] = Field(default_factory=list, description="Tags for this object instance")
    vibe: int = Field(default=0, ge=0, le=255, description="Vibe value for this object instance")
    collective: Optional[str] = Field(
        default=None,
        description="Name of collective this object belongs to.",
    )
    aoes: dict[str, AOEConfig] = Field(
        default_factory=dict,
        description="Named AOE configs this object emits to targets within range (name -> config)",
    )
    inventory: InventoryConfig = Field(default_factory=InventoryConfig)

    # Handlers - dict[name, Handler] for backwards compatibility
    handlers: dict[str, Handler] = Field(
        default_factory=dict,
        description="Handlers triggered when an agent moves onto this object (name -> handler)",
    )

    # Handler types on GridObject (name -> handler)
    on_use_handlers: dict[str, Handler] = Field(
        default_factory=dict,
        description="Handlers triggered when agent uses/activates this object (context: actor=agent, target=this)",
    )

    @model_validator(mode="after")
    def _defaults_from_name(self) -> "GridObjectConfig":
        if not self.map_name:
            self.map_name = self.name
        if not self.render_name:
            self.render_name = self.name
        # Add collective tag if collective is set
        if self.collective:
            collective_tag = Tag(f"collective:{self.collective}")
            if collective_tag not in self.tags:
                self.tags = self.tags + [collective_tag]
        # Type tags are auto-generated during C++ conversion via typeTag(object_type)
        return self


class WallConfig(GridObjectConfig):
    """Python wall/block configuration."""

    # This is used to discriminate between different GridObjectConfig subclasses in Pydantic.
    # See AnyGridObjectConfig.
    # Please don't use this for anything game related.
    pydantic_type: Literal["wall"] = "wall"
    name: str = Field(default="wall")


class AgentConfig(GridObjectConfig):
    """Python agent configuration.

    Inherits from GridObjectConfig to share tags, collective, vibe, inventory, and handler fields.
    """

    name: str = Field(default="agent")
    team_id: int = Field(default=0, ge=0, description="Team ID for grouping agents")
    rewards: dict[str, AgentReward] = Field(default_factory=dict)
    freeze_duration: int = Field(default=10, ge=-1)
    on_tick: dict[str, Handler] = Field(
        default_factory=dict,
        description="Handlers run every tick with actor=target=this agent (name -> handler)",
    )


class ProtocolConfig(Config):
    # Note that `vibes` implicitly also sets a minimum number of agents. So min_agents is useful
    # when you want to set a minimum that's higher than the number of vibes.
    min_agents: int = Field(default=0, ge=0, description="Number of agents required to use this protocol")
    vibes: list[str] = Field(default_factory=list)
    input_resources: dict[str, int] = Field(default_factory=dict)
    output_resources: dict[str, int] = Field(default_factory=dict)
    cooldown: int = Field(ge=0, default=0)


class AssemblerConfig(GridObjectConfig):
    """Python assembler configuration."""

    # This is used to discriminate between different GridObjectConfig subclasses in Pydantic.
    # See AnyGridObjectConfig.
    # Please don't use this for anything game related.
    pydantic_type: Literal["assembler"] = "assembler"
    # No default name -- we want to make sure that meaningful names are provided.
    protocols: list[ProtocolConfig] = Field(
        default_factory=list,
        description="Protocols in reverse order of priority.",
    )
    allow_partial_usage: bool = Field(
        default=False,
        description=(
            "Allow assembler to be used during cooldown with scaled resource requirements/outputs. "
            "This makes less sense if the assembler has multiple protocols."
        ),
    )
    max_uses: int = Field(default=0, ge=0, description="Maximum number of uses (0 = unlimited)")
    chest_search_distance: int = Field(
        default=0,
        ge=0,
        description="Distance within which assembler can use inventories from chests",
    )


class ChestConfig(GridObjectConfig):
    """Python chest configuration for multi-resource chests."""

    # This is used to discriminate between different GridObjectConfig subclasses in Pydantic.
    # See AnyGridObjectConfig.
    # Please don't use this for anything game related.
    pydantic_type: Literal["chest"] = "chest"
    name: str = Field(default="chest")

    # Vibe-based transfers: vibe -> resource -> delta
    vibe_transfers: dict[str, dict[str, int]] = Field(
        default_factory=dict,
        description=(
            "Map from vibe to resource deltas. "
            "E.g., {'carbon': {'carbon': 10, 'energy': -5}} deposits 10 carbon and withdraws 5 energy when "
            "showing carbon vibe"
        ),
    )

    inventory: InventoryConfig = Field(default_factory=InventoryConfig, description="Inventory configuration")


class CollectiveChestConfig(GridObjectConfig):
    """Chest that interacts with collectives."""

    pydantic_type: Literal["collective_chest"] = "collective_chest"
    name: str = Field(default="collective_chest")


class CollectiveConfig(Config):
    """
    Configuration for a shared inventory (Collective).

    Collective provides a shared inventory that multiple grid objects can access.
    Objects are associated with a collective by setting collective="name" in their config.

    Note: Collective name is typically provided as the dict key when defining collectives.
    """

    name: str = Field(default="", description="Unique name for this collective (typically set from dict key)")
    inventory: InventoryConfig = Field(default_factory=InventoryConfig, description="Inventory configuration")


# Note: GridObjectConfig is included to allow direct use of the base class for simple objects
# that only need handlers/aoes without specialized features like protocols or inventory.
AnyGridObjectConfig = Union[
    WallConfig,
    AssemblerConfig,
    ChestConfig,
    CollectiveChestConfig,
    GridObjectConfig,
]


class GameConfig(Config):
    """Python game configuration.

    Note: Type IDs are automatically assigned during validation when the GameConfig
    is constructed. If you need to add objects after construction, create a new
    GameConfig instance rather than modifying the objects dict post-construction.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    resource_names: list[str] = Field(
        default=[
            "ore_red",
            "ore_blue",
            "ore_green",
            "battery_red",
            "battery_blue",
            "battery_green",
            "heart",
            "armor",
            "laser",
            "blueprint",
        ]
    )
    vibe_names: list[str] = Field(default_factory=list)
    num_agents: int = Field(ge=1, default=24)
    # max_steps = zero means "no limit"
    max_steps: int = Field(ge=0, default=10000)
    # default is that we terminate / use "done" vs truncation
    episode_truncates: bool = Field(default=False)
    obs: ObsConfig = Field(default_factory=ObsConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    agents: list[AgentConfig] = Field(default_factory=list)
    actions: ActionsConfig = Field(default_factory=lambda: ActionsConfig())
    objects: dict[str, AnyGridObjectConfig] = Field(default_factory=dict)
    # these are not used in the C++ code, but we allow them to be set for other uses.
    # E.g., templates can use params as a place  where values are expected to be written,
    # and other parts of the template can read from there.
    params: Optional[Any] = None

    # Collectives - shared inventories that grid objects can belong to
    collectives: dict[str, CollectiveConfig] = Field(
        default_factory=dict,
        description="Collectives (shared inventories) that grid objects can belong to (name -> config)",
    )

    # Events - timestep-triggered effects that apply mutations to filtered objects
    events: dict[str, EventConfig] = Field(
        default_factory=dict,
        description="Events that fire at specific timesteps, applying mutations to filtered objects.",
    )

    # Map builder configuration - accepts any MapBuilder config
    map_builder: AnyMapBuilderConfig = Field(default_factory=lambda: RandomMapBuilder.Config(agents=24))

    protocol_details_obs: bool = Field(
        default=True, description="Objects show their protocol inputs and outputs when observed"
    )

    reward_estimates: Optional[dict[str, float]] = Field(default=None)

    # Explicit list of tags used in the game. All tag references in filters/mutations
    # must refer to one of these, or obj.tags, or the implicit type:object_type tag.
    tags: list[Tag] = Field(default_factory=list, description="Explicit list of tags used in the game")

    @model_validator(mode="after")
    def _compute_feature_ids(self) -> "GameConfig":
        self.vibe_names = [vibe.name for vibe in self.actions.change_vibe.vibes]
        return self

    def id_map(self) -> "IdMap":
        """Get the observation feature ID map for this configuration."""
        return IdMap(self)


class MettaGridConfig(Config):
    """Environment configuration."""

    label: str = Field(default="mettagrid")
    game: GameConfig = Field(default_factory=GameConfig)
    desync_episodes: bool = Field(default=True)

    def with_ascii_map(self, map_data: list[list[str]], char_to_map_name: dict[str, str]) -> "MettaGridConfig":
        self.game.map_builder = AsciiMapBuilder.Config(
            map_data=map_data,
            char_to_map_name=char_to_map_name,
        )
        return self

    @staticmethod
    def EmptyRoom(
        num_agents: int, width: int = 10, height: int = 10, border_width: int = 1, with_walls: bool = False
    ) -> "MettaGridConfig":
        """Create an empty room environment configuration."""
        map_builder = RandomMapBuilder.Config(agents=num_agents, width=width, height=height, border_width=border_width)
        actions = ActionsConfig(move=MoveActionConfig(), change_vibe=ChangeVibeActionConfig())
        objects = {}
        if border_width > 0 or with_walls:
            objects["wall"] = WallConfig(render_symbol="⬛")
        return MettaGridConfig(
            game=GameConfig(map_builder=map_builder, actions=actions, num_agents=num_agents, objects=objects)
        )
