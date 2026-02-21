from enum import Enum
from typing import Any, NotRequired, Optional, TypeAlias, TypedDict, Union, overload

import numpy as np

# Type alias for clarity
StatsDict: TypeAlias = dict[str, float]

# GameValue enums and config

class GameValueScope(Enum):
    """Scope of game value."""

    AGENT = ...
    GAME = ...
    COLLECTIVE = ...

class InventoryValueConfig:
    def __init__(self) -> None: ...
    scope: GameValueScope
    id: int

class StatValueConfig:
    def __init__(self) -> None: ...
    scope: GameValueScope
    id: int
    delta: bool
    stat_name: str

class TagCountValueConfig:
    def __init__(self) -> None: ...
    id: int

class ConstValueConfig:
    def __init__(self) -> None: ...
    value: float

class QueryInventoryValueConfig:
    def __init__(self) -> None: ...
    id: int
    def set_query(self, query: Any) -> None: ...

GameValueConfig: TypeAlias = Union[
    InventoryValueConfig, StatValueConfig, TagCountValueConfig, ConstValueConfig, QueryInventoryValueConfig
]

# Handler enums from handler_config.hpp

class EntityRef(Enum):
    """Entity reference for resolving actor/target in filters and mutations."""

    actor = ...
    target = ...
    actor_collective = ...
    target_collective = ...

class AlignmentCondition(Enum):
    """Alignment conditions for AlignmentFilter."""

    aligned = ...
    unaligned = ...
    same_collective = ...
    different_collective = ...

class AlignTo(Enum):
    """Align-to options for AlignmentMutation."""

    actor_collective = ...
    none = ...

class HandlerMode(Enum):
    """Handler dispatch mode for MultiHandler."""

    FirstMatch = ...
    All = ...

class StatsTarget(Enum):
    """Stats target for StatsMutation."""

    game = ...
    agent = ...
    collective = ...

class StatsEntity(Enum):
    """Stats entity for StatsMutation."""

    target = ...
    actor = ...

class QueryOrderBy(Enum):
    none = ...
    random = ...

# Handler filter configs

class VibeFilterConfig:
    def __init__(
        self,
        entity: EntityRef = ...,
        vibe_id: int = 0,
    ) -> None: ...
    entity: EntityRef
    vibe_id: int

class ResourceFilterConfig:
    def __init__(
        self,
        entity: EntityRef = ...,
        resource_id: int = 0,
        min_amount: int = 1,
    ) -> None: ...
    entity: EntityRef
    resource_id: int
    min_amount: int

class AlignmentFilterConfig:
    def __init__(
        self,
        condition: AlignmentCondition = ...,
    ) -> None: ...
    condition: AlignmentCondition
    collective_id: int

class SharedTagPrefixFilterConfig:
    def __init__(
        self,
        tag_ids: list[int] = ...,
    ) -> None: ...
    tag_ids: list[int]

class TagPrefixFilterConfig:
    def __init__(
        self,
        entity: EntityRef = ...,
        tag_ids: list[int] = ...,
    ) -> None: ...
    entity: EntityRef
    tag_ids: list[int]

class GameValueFilterConfig:
    def __init__(
        self,
        value: GameValueConfig = ...,
        threshold: float = 0.0,
        entity: EntityRef = ...,
    ) -> None: ...
    value: GameValueConfig
    threshold: float
    entity: EntityRef

class QueryConfigHolder:
    def __init__(self) -> None: ...

class TagQueryConfig:
    def __init__(self) -> None: ...
    tag_id: int
    max_items: int
    order_by: QueryOrderBy
    def add_tag_prefix_filter(self, filter: TagPrefixFilterConfig) -> None: ...
    def add_vibe_filter(self, filter: VibeFilterConfig) -> None: ...
    def add_resource_filter(self, filter: ResourceFilterConfig) -> None: ...
    def add_max_distance_filter(self, filter: "MaxDistanceFilterConfig") -> None: ...
    def add_neg_filter(self, filter: "NegFilterConfig") -> None: ...
    def add_or_filter(self, filter: "OrFilterConfig") -> None: ...
    def add_game_value_filter(self, filter: GameValueFilterConfig) -> None: ...
    def add_shared_tag_prefix_filter(self, filter: SharedTagPrefixFilterConfig) -> None: ...

class MaxDistanceFilterConfig:
    def __init__(self) -> None: ...
    entity: EntityRef
    radius: int
    def set_source(self, source: QueryConfigHolder) -> None: ...

class ClosureQueryConfig:
    def __init__(self) -> None: ...
    max_items: int
    order_by: QueryOrderBy
    def set_source(self, source: QueryConfigHolder) -> None: ...
    def set_candidates(self, candidates: QueryConfigHolder) -> None: ...
    def add_edge_max_distance_filter(self, filter: "MaxDistanceFilterConfig") -> None: ...
    def add_edge_tag_prefix_filter(self, filter: TagPrefixFilterConfig) -> None: ...
    def add_edge_alignment_filter(self, filter: AlignmentFilterConfig) -> None: ...
    def add_edge_neg_filter(self, filter: "NegFilterConfig") -> None: ...
    def add_edge_or_filter(self, filter: "OrFilterConfig") -> None: ...
    def add_edge_shared_tag_prefix_filter(self, filter: SharedTagPrefixFilterConfig) -> None: ...
    def add_edge_vibe_filter(self, filter: VibeFilterConfig) -> None: ...
    def add_edge_resource_filter(self, filter: ResourceFilterConfig) -> None: ...
    def add_edge_game_value_filter(self, filter: GameValueFilterConfig) -> None: ...
    def add_result_tag_prefix_filter(self, filter: TagPrefixFilterConfig) -> None: ...
    def add_result_shared_tag_prefix_filter(self, filter: SharedTagPrefixFilterConfig) -> None: ...
    def add_result_neg_filter(self, filter: "NegFilterConfig") -> None: ...
    def add_result_or_filter(self, filter: "OrFilterConfig") -> None: ...
    def add_result_resource_filter(self, filter: ResourceFilterConfig) -> None: ...
    def add_result_game_value_filter(self, filter: GameValueFilterConfig) -> None: ...
    def add_result_alignment_filter(self, filter: AlignmentFilterConfig) -> None: ...
    def add_result_vibe_filter(self, filter: VibeFilterConfig) -> None: ...
    def add_result_max_distance_filter(self, filter: "MaxDistanceFilterConfig") -> None: ...

class FilteredQueryConfig:
    def __init__(self) -> None: ...
    max_items: int
    order_by: QueryOrderBy
    def set_source(self, source: QueryConfigHolder) -> None: ...
    def add_tag_prefix_filter(self, filter: TagPrefixFilterConfig) -> None: ...
    def add_shared_tag_prefix_filter(self, filter: SharedTagPrefixFilterConfig) -> None: ...
    def add_vibe_filter(self, filter: VibeFilterConfig) -> None: ...
    def add_resource_filter(self, filter: ResourceFilterConfig) -> None: ...
    def add_max_distance_filter(self, filter: "MaxDistanceFilterConfig") -> None: ...
    def add_neg_filter(self, filter: "NegFilterConfig") -> None: ...
    def add_or_filter(self, filter: "OrFilterConfig") -> None: ...
    def add_game_value_filter(self, filter: GameValueFilterConfig) -> None: ...
    def add_alignment_filter(self, filter: AlignmentFilterConfig) -> None: ...

def make_query_config(query: TagQueryConfig | ClosureQueryConfig | FilteredQueryConfig) -> QueryConfigHolder: ...

class NegFilterConfig:
    def __init__(self) -> None: ...
    inner: list
    def add_alignment_filter(self, filter: AlignmentFilterConfig) -> None: ...
    def add_vibe_filter(self, filter: VibeFilterConfig) -> None: ...
    def add_resource_filter(self, filter: ResourceFilterConfig) -> None: ...
    def add_max_distance_filter(self, filter: MaxDistanceFilterConfig) -> None: ...
    def add_game_value_filter(self, filter: GameValueFilterConfig) -> None: ...
    def add_shared_tag_prefix_filter(self, filter: SharedTagPrefixFilterConfig) -> None: ...
    def add_tag_prefix_filter(self, filter: TagPrefixFilterConfig) -> None: ...
    def add_neg_filter(self, filter: NegFilterConfig) -> None: ...
    def add_or_filter(self, filter: "OrFilterConfig") -> None: ...

class OrFilterConfig:
    def __init__(self) -> None: ...
    inner: list
    def add_alignment_filter(self, filter: AlignmentFilterConfig) -> None: ...
    def add_vibe_filter(self, filter: VibeFilterConfig) -> None: ...
    def add_resource_filter(self, filter: ResourceFilterConfig) -> None: ...
    def add_max_distance_filter(self, filter: MaxDistanceFilterConfig) -> None: ...
    def add_game_value_filter(self, filter: GameValueFilterConfig) -> None: ...
    def add_shared_tag_prefix_filter(self, filter: SharedTagPrefixFilterConfig) -> None: ...
    def add_tag_prefix_filter(self, filter: TagPrefixFilterConfig) -> None: ...
    def add_neg_filter(self, filter: NegFilterConfig) -> None: ...
    def add_or_filter(self, filter: "OrFilterConfig") -> None: ...

# Handler mutation configs

class ResourceDeltaMutationConfig:
    def __init__(
        self,
        entity: EntityRef = ...,
        resource_id: int = 0,
        delta: int = 0,
    ) -> None: ...
    entity: EntityRef
    resource_id: int
    delta: int

class ResourceTransferMutationConfig:
    def __init__(
        self,
        source: EntityRef = ...,
        destination: EntityRef = ...,
        resource_id: int = 0,
        amount: int = -1,
        remove_source_when_empty: bool = False,
    ) -> None: ...
    source: EntityRef
    destination: EntityRef
    resource_id: int
    amount: int
    remove_source_when_empty: bool

class AlignmentMutationConfig:
    def __init__(
        self,
        align_to: AlignTo = ...,
    ) -> None: ...
    align_to: AlignTo
    collective_id: int

class FreezeMutationConfig:
    def __init__(
        self,
        duration: int = 1,
    ) -> None: ...
    duration: int

class ClearInventoryMutationConfig:
    def __init__(
        self,
        entity: EntityRef = ...,
        resource_ids: list[int] = ...,
    ) -> None: ...
    entity: EntityRef
    resource_ids: list[int]

class AttackMutationConfig:
    def __init__(
        self,
        weapon_resource: int = -1,
        armor_resource: int = -1,
        health_resource: int = -1,
        damage_multiplier_pct: int = 100,
    ) -> None: ...
    weapon_resource: int
    armor_resource: int
    health_resource: int
    damage_multiplier_pct: int

class StatsMutationConfig:
    def __init__(
        self,
        stat_name: str = "",
        delta: float = 1.0,
        target: StatsTarget = ...,
        entity: StatsEntity = ...,
    ) -> None: ...
    stat_name: str
    delta: float
    target: StatsTarget
    entity: StatsEntity

class AddTagMutationConfig:
    def __init__(
        self,
        entity: EntityRef = ...,
        tag_id: int = -1,
    ) -> None: ...
    entity: EntityRef
    tag_id: int

class GameValueMutationConfig:
    def __init__(
        self,
        value: GameValueConfig = ...,
        target: EntityRef = ...,
        source: GameValueConfig = ...,
    ) -> None: ...
    value: GameValueConfig
    target: EntityRef
    source: GameValueConfig

class RemoveTagMutationConfig:
    def __init__(
        self,
        entity: EntityRef = ...,
        tag_id: int = -1,
    ) -> None: ...
    entity: EntityRef
    tag_id: int

class RemoveTagsWithPrefixMutationConfig:
    def __init__(
        self,
        entity: EntityRef = ...,
        tag_ids: list[int] = ...,
    ) -> None: ...
    entity: EntityRef
    tag_ids: list[int]

class RecomputeMaterializedQueryMutationConfig:
    def __init__(self) -> None: ...
    tag_id: int

class QueryInventoryMutationConfig:
    def __init__(self) -> None: ...
    deltas: list[tuple[int, int]]
    source: EntityRef
    has_source: bool
    def set_query(self, query: QueryConfigHolder) -> None: ...

# Handler config

class HandlerConfig:
    def __init__(self, name: str = "") -> None: ...
    name: str
    filters: list
    mutations: list

    def add_alignment_filter(self, filter: AlignmentFilterConfig) -> None: ...
    def add_resource_filter(self, filter: ResourceFilterConfig) -> None: ...
    def add_vibe_filter(self, filter: VibeFilterConfig) -> None: ...
    def add_max_distance_filter(self, filter: MaxDistanceFilterConfig) -> None: ...
    def add_game_value_filter(self, filter: GameValueFilterConfig) -> None: ...
    def add_neg_filter(self, filter: NegFilterConfig) -> None: ...
    def add_or_filter(self, filter: OrFilterConfig) -> None: ...
    def add_shared_tag_prefix_filter(self, filter: SharedTagPrefixFilterConfig) -> None: ...
    def add_tag_prefix_filter(self, filter: TagPrefixFilterConfig) -> None: ...
    def add_resource_delta_mutation(self, mutation: ResourceDeltaMutationConfig) -> None: ...
    def add_resource_transfer_mutation(self, mutation: ResourceTransferMutationConfig) -> None: ...
    def add_alignment_mutation(self, mutation: AlignmentMutationConfig) -> None: ...
    def add_freeze_mutation(self, mutation: FreezeMutationConfig) -> None: ...
    def add_clear_inventory_mutation(self, mutation: ClearInventoryMutationConfig) -> None: ...
    def add_attack_mutation(self, mutation: AttackMutationConfig) -> None: ...
    def add_stats_mutation(self, mutation: StatsMutationConfig) -> None: ...
    def add_add_tag_mutation(self, mutation: AddTagMutationConfig) -> None: ...
    def add_remove_tag_mutation(self, mutation: RemoveTagMutationConfig) -> None: ...
    def add_game_value_mutation(self, mutation: GameValueMutationConfig) -> None: ...
    def add_recompute_materialized_query_mutation(self, mutation: RecomputeMaterializedQueryMutationConfig) -> None: ...
    def add_query_inventory_mutation(self, mutation: QueryInventoryMutationConfig) -> None: ...
    def add_remove_tags_with_prefix_mutation(self, mutation: RemoveTagsWithPrefixMutationConfig) -> None: ...

class ResourceDelta:
    def __init__(self, resource_id: int = 0, delta: int = 0) -> None: ...
    resource_id: int
    delta: int

class AOEConfig(HandlerConfig):
    """AOE configuration inheriting filters/mutations from HandlerConfig."""

    def __init__(self) -> None: ...
    radius: int
    is_static: bool
    effect_self: bool
    controls_territory: bool
    presence_deltas: list[ResourceDelta]

class EventConfig(HandlerConfig):
    """Configuration for timestep-triggered events."""

    def __init__(self, name: str = "") -> None: ...
    name: str
    def set_target_query(self, query: QueryConfigHolder) -> None: ...
    timesteps: list[int]
    max_targets: int
    fallback: str

# Handler classes

class Handler:
    """Single handler with filters and mutations."""

    def __init__(self, config: HandlerConfig, tag_index: Any = None) -> None: ...
    @property
    def name(self) -> str: ...
    def try_apply(self, ctx: Any) -> bool: ...

class MultiHandler(Handler):
    """Dispatches to multiple handlers with configurable mode."""

    def __init__(self, handlers: list[Handler], mode: HandlerMode) -> None: ...
    @property
    def mode(self) -> HandlerMode: ...
    def try_apply(self, ctx: Any) -> bool: ...
    def __len__(self) -> int: ...
    def __bool__(self) -> bool: ...

# Data types exported from C++
dtype_observations: np.dtype
dtype_terminals: np.dtype
dtype_truncations: np.dtype
dtype_rewards: np.dtype
dtype_actions: np.dtype
dtype_masks: np.dtype
dtype_success: np.dtype

class EpisodeStats(TypedDict):
    game: StatsDict
    agent: list[StatsDict]
    collective: NotRequired[dict[str, StatsDict]]

class PackedCoordinate:
    """Packed coordinate encoding utilities."""

    MAX_PACKABLE_COORD: int
    GLOBAL_LOCATION: int

    @staticmethod
    def pack(row: int, col: int) -> int:
        """Pack (row, col) coordinates into a single byte.
        Args:
            row: Row coordinate (0-14)
            col: Column coordinate (0-14)
        Returns:
            Packed byte value
        Note:
            The value 0xFF is reserved to indicate 'empty'.
        Raises:
            ValueError: If row or col > 14
        """
        ...

    @staticmethod
    def unpack(packed: int) -> Optional[tuple[int, int]]:
        """Unpack byte into (row, col) tuple or None if empty.
        Args:
            packed: Packed coordinate byte
        Returns:
            (row, col) tuple or None if empty location
        """
        ...

    @staticmethod
    def is_empty(packed: int) -> bool:
        """Check if packed value represents empty location (0xFF)."""
        ...

    @staticmethod
    def is_global(packed: int) -> bool:
        """Check if packed value represents global token location (0xFE)."""
        ...

class GridObjectConfig:
    def __init__(
        self,
        type_id: int,
        type_name: str,
        initial_vibe: int = 0,
    ) -> None: ...
    type_id: int
    type_name: str
    tag_ids: list[int]
    initial_vibe: int
    collective_id: int
    on_use_handler: Handler | None
    aoe_configs: list[AOEConfig]
    initial_inventory: dict[int, int]
    inventory_config: InventoryConfig

class LimitDef:
    def __init__(
        self,
        resources: list[int] = [],
        min_limit: int = 0,
        max_limit: int = 65535,
        modifiers: dict[int, int] = {},
    ) -> None: ...
    resources: list[int]
    min_limit: int
    max_limit: int
    modifiers: dict[int, int]

class InventoryConfig:
    def __init__(self) -> None: ...
    limit_defs: list[LimitDef]

class AggregationMode(Enum):
    SUM = ...
    SUM_LOGS = ...

class RewardEntry:
    def __init__(self) -> None: ...
    numerators: list[GameValueConfig]
    denominators: list[GameValueConfig]
    weight: float
    max_value: float
    has_max: bool
    accumulate: bool
    aggregation_mode: AggregationMode

class RewardConfig:
    def __init__(self) -> None: ...
    entries: list[RewardEntry]

class WallConfig(GridObjectConfig):
    def __init__(self, type_id: int, type_name: str, initial_vibe: int = 0): ...
    type_id: int
    type_name: str
    tag_ids: list[int]
    initial_vibe: int

class AgentConfig(GridObjectConfig):
    def __init__(
        self,
        type_id: int,
        type_name: str = "agent",
        group_id: int = ...,
        group_name: str = ...,
        freeze_duration: int = 0,
        initial_vibe: int = 0,
        inventory_config: InventoryConfig = ...,
        reward_config: RewardConfig = ...,
        initial_inventory: dict[int, int] = {},
        on_tick: list[HandlerConfig] | None = None,
    ) -> None: ...
    type_id: int
    type_name: str
    tag_ids: list[int]
    initial_vibe: int
    group_id: int
    group_name: str
    freeze_duration: int
    inventory_config: InventoryConfig
    reward_config: RewardConfig
    initial_inventory: dict[int, int]
    on_tick: list[HandlerConfig]

class ActionConfig:
    def __init__(
        self,
        required_resources: dict[int, int] = {},
        consumed_resources: dict[int, int] = {},
    ) -> None: ...
    required_resources: dict[int, int]
    consumed_resources: dict[int, int]

class CollectiveConfig:
    def __init__(self, name: str = "") -> None: ...
    name: str
    inventory_config: InventoryConfig
    initial_inventory: dict[int, int]

class AttackOutcome:
    def __init__(
        self,
        actor_inv_delta: dict[int, int] = {},
        target_inv_delta: dict[int, int] = {},
        loot: list[int] = [],
        freeze: int = 0,
    ) -> None: ...
    actor_inv_delta: dict[int, int]
    target_inv_delta: dict[int, int]
    loot: list[int]
    freeze: int

class AttackActionConfig(ActionConfig):
    def __init__(
        self,
        required_resources: dict[int, int] = {},
        consumed_resources: dict[int, int] = {},
        defense_resources: dict[int, int] = {},
        armor_resources: dict[int, int] = {},
        weapon_resources: dict[int, int] = {},
        success: AttackOutcome = ...,
        enabled: bool = True,
        vibes: list[int] = [],
        vibe_bonus: dict[int, int] = {},
    ) -> None: ...
    defense_resources: dict[int, int]
    armor_resources: dict[int, int]
    weapon_resources: dict[int, int]
    success: AttackOutcome
    enabled: bool
    vibes: list[int]
    vibe_bonus: dict[int, int]

class MoveActionConfig(ActionConfig):
    def __init__(
        self,
        allowed_directions: list[str] = ["north", "south", "west", "east"],
        required_resources: dict[int, int] = {},
        consumed_resources: dict[int, int] = {},
    ) -> None: ...
    allowed_directions: list[str]

class ChangeVibeActionConfig(ActionConfig):
    def __init__(
        self,
        required_resources: dict[int, int] = {},
        consumed_resources: dict[int, int] = {},
        number_of_vibes: int = ...,
    ) -> None: ...
    number_of_vibes: int

class ObsValueConfig:
    def __init__(self) -> None: ...
    value: GameValueConfig
    feature_id: int

class GlobalObsConfig:
    def __init__(
        self,
        episode_completion_pct: bool = True,
        last_action: bool = True,
        last_action_move: bool = False,
        last_reward: bool = True,
        goal_obs: bool = False,
        local_position: bool = False,
        obs: list[ObsValueConfig] = ...,
    ) -> None: ...
    episode_completion_pct: bool
    last_action: bool
    last_action_move: bool
    last_reward: bool
    goal_obs: bool
    local_position: bool
    obs: list[ObsValueConfig]

class GameConfig:
    def __init__(
        self,
        num_agents: int,
        max_steps: int,
        episode_truncates: bool,
        obs_width: int,
        obs_height: int,
        resource_names: list[str],
        vibe_names: list[str],
        num_observation_tokens: int,
        global_obs: GlobalObsConfig,
        feature_ids: dict[str, int],
        actions: dict[str, ActionConfig],
        objects: dict[str, GridObjectConfig],
        tag_id_map: dict[int, str] | None = None,
        collectives: dict[str, CollectiveConfig] | None = None,
        protocol_details_obs: bool = True,
        reward_estimates: Optional[dict[str, float]] = None,
        token_value_base: int = 256,
    ) -> None: ...
    num_agents: int
    max_steps: int
    episode_truncates: bool
    obs_width: int
    obs_height: int
    resource_names: list[str]
    vibe_names: list[str]
    num_observation_tokens: int
    global_obs: GlobalObsConfig
    feature_ids: dict[str, int]
    tag_id_map: dict[int, str]
    collectives: dict[str, CollectiveConfig]
    # FEATURE FLAGS
    protocol_details_obs: bool
    reward_estimates: Optional[dict[str, float]]
    token_value_base: int

class MettaGrid:
    obs_width: int
    obs_height: int
    max_steps: int
    current_step: int
    map_width: int
    map_height: int
    num_agents: int
    object_type_names: list[str]

    def __init__(self, env_cfg: GameConfig, map: list, seed: int) -> None: ...
    def step(self) -> None: ...
    @overload
    def set_buffers(
        self,
        observations: np.ndarray,
        terminals: np.ndarray,
        truncations: np.ndarray,
        rewards: np.ndarray,
        actions: np.ndarray,
        vibe_actions: np.ndarray,
    ) -> None: ...
    @overload
    def set_buffers(
        self,
        observations: np.ndarray,
        terminals: np.ndarray,
        truncations: np.ndarray,
        rewards: np.ndarray,
        actions: np.ndarray,
    ) -> None: ...
    def grid_objects(
        self,
        min_row: int = -1,
        max_row: int = -1,
        min_col: int = -1,
        max_col: int = -1,
        ignore_types: list[str] = [],
    ) -> dict[int, dict]: ...
    def observations(self) -> np.ndarray: ...
    def terminals(self) -> np.ndarray: ...
    def truncations(self) -> np.ndarray: ...
    def rewards(self) -> np.ndarray: ...
    def masks(self) -> np.ndarray: ...
    def actions(self) -> np.ndarray: ...
    def vibe_actions(self) -> np.ndarray: ...
    def get_episode_rewards(self) -> np.ndarray: ...
    def get_episode_stats(self) -> EpisodeStats: ...
    def get_game_stat(self, key: str) -> float | None: ...
    def get_agent_stat(self, agent_id: int, key: str) -> float | None: ...
    def get_collective_stat(self, collective_name: str, key: str) -> float | None: ...
    def action_success(self) -> list[bool]: ...
    def set_inventory(self, agent_id: int, inventory: dict[int, int]) -> None: ...
    def get_collective_inventories(self) -> dict[str, dict[str, int]]: ...
