from enum import Enum
from typing import NotRequired, Optional, TypeAlias, TypedDict

import numpy as np

# Type alias for clarity
StatsDict: TypeAlias = dict[str, float]

# GameValue enums and config

class GameValueType(Enum):
    """Type of game value."""

    INVENTORY = ...
    STAT = ...
    TAG_COUNT = ...

class GameValueScope(Enum):
    """Scope of game value."""

    AGENT = ...
    COLLECTIVE = ...
    GAME = ...

class GameValueConfig:
    def __init__(self) -> None: ...
    type: GameValueType
    scope: GameValueScope
    id: int
    delta: bool
    stat_name: str

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

class HandlerType(Enum):
    """Handler type enum."""

    on_use = ...
    aoe = ...

class StatsTarget(Enum):
    """Stats target for StatsMutation."""

    game = ...
    agent = ...
    collective = ...

class StatsEntity(Enum):
    """Stats entity for StatsMutation."""

    target = ...
    actor = ...

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

class TagFilterConfig:
    def __init__(
        self,
        entity: EntityRef = ...,
        tag_id: int = 0,
    ) -> None: ...
    entity: EntityRef
    tag_id: int

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

class NearFilterConfig:
    def __init__(
        self,
        entity: EntityRef = ...,
        radius: int = 1,
        target_tag: int = -1,
    ) -> None: ...
    entity: EntityRef
    radius: int
    target_tag: int
    filters: list
    def add_alignment_filter(self, filter: AlignmentFilterConfig) -> None: ...
    def add_vibe_filter(self, filter: VibeFilterConfig) -> None: ...
    def add_resource_filter(self, filter: ResourceFilterConfig) -> None: ...
    def add_tag_filter(self, filter: TagFilterConfig) -> None: ...

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
        delta: float = 0.0,
        entity: EntityRef = ...,
    ) -> None: ...
    value: GameValueConfig
    delta: float
    entity: EntityRef

class RemoveTagMutationConfig:
    def __init__(
        self,
        entity: EntityRef = ...,
        tag_id: int = -1,
    ) -> None: ...
    entity: EntityRef
    tag_id: int

# Handler config

class HandlerConfig:
    def __init__(self, name: str = "") -> None: ...
    name: str
    filters: list
    mutations: list
    radius: int

    def add_alignment_filter(self, filter: AlignmentFilterConfig) -> None: ...
    def add_resource_filter(self, filter: ResourceFilterConfig) -> None: ...
    def add_vibe_filter(self, filter: VibeFilterConfig) -> None: ...
    def add_tag_filter(self, filter: TagFilterConfig) -> None: ...
    def add_near_filter(self, filter: NearFilterConfig) -> None: ...
    def add_game_value_filter(self, filter: GameValueFilterConfig) -> None: ...
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

class ResourceDelta:
    def __init__(self, resource_id: int = 0, delta: int = 0) -> None: ...
    resource_id: int
    delta: int

class AOEConfig(HandlerConfig):
    """AOE configuration inheriting filters/mutations from HandlerConfig."""

    def __init__(self) -> None: ...
    is_static: bool
    effect_self: bool
    presence_deltas: list[ResourceDelta]

class EventConfig(HandlerConfig):
    """Configuration for timestep-triggered events."""

    def __init__(self, name: str = "") -> None: ...
    name: str
    target_tag_id: int
    timesteps: list[int]
    max_targets: int
    fallback: str

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
        """Check if packed value represents empty location."""
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
    on_use_handlers: list[HandlerConfig]
    aoe_configs: list[AOEConfig]

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

class RewardEntry:
    def __init__(self) -> None: ...
    numerator: GameValueConfig
    denominators: list[GameValueConfig]
    weight: float
    max_value: float
    has_max: bool

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

class Protocol:
    def __init__(self) -> None: ...
    min_agents: int
    vibes: list[int]
    input_resources: dict[int, int]
    output_resources: dict[int, int]
    cooldown: int

class AssemblerConfig(GridObjectConfig):
    def __init__(
        self,
        type_id: int,
        type_name: str,
        initial_vibe: int = 0,
    ) -> None: ...
    type_id: int
    type_name: str
    tag_ids: list[int]
    protocols: list[Protocol]
    allow_partial_usage: bool
    max_uses: int
    clip_immune: bool
    start_clipped: bool
    chest_search_distance: int
    initial_vibe: int

class ChestConfig(GridObjectConfig):
    def __init__(
        self,
        type_id: int,
        type_name: str,
        initial_vibe: int = 0,
    ) -> None: ...
    type_id: int
    type_name: str
    tag_ids: list[int]
    vibe_transfers: dict[int, dict[int, int]]
    initial_inventory: dict[int, int]
    inventory_config: InventoryConfig
    initial_vibe: int

class ClipperConfig:
    def __init__(self) -> None: ...
    unclipping_protocols: list[Protocol]
    length_scale: int
    scaled_cutoff_distance: int
    clip_period: int

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

class VibeTransferEffect:
    def __init__(
        self,
        target_deltas: dict[int, int] = {},
        actor_deltas: dict[int, int] = {},
    ) -> None: ...
    target_deltas: dict[int, int]
    actor_deltas: dict[int, int]

class TransferActionConfig(ActionConfig):
    def __init__(
        self,
        required_resources: dict[int, int] = {},
        vibe_transfers: dict[int, VibeTransferEffect] = {},
        enabled: bool = True,
    ) -> None: ...
    vibe_transfers: dict[int, VibeTransferEffect]
    enabled: bool

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
        last_reward: bool = True,
        compass: bool = False,
        goal_obs: bool = False,
        local_position: bool = False,
        obs: list[ObsValueConfig] = ...,
    ) -> None: ...
    episode_completion_pct: bool
    last_action: bool
    last_reward: bool
    compass: bool
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
        clipper: Optional[ClipperConfig] = None,
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
    clipper: Optional[ClipperConfig]
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
    def get_episode_rewards(self) -> np.ndarray: ...
    def get_episode_stats(self) -> EpisodeStats: ...
    def action_success(self) -> list[bool]: ...
    def set_inventory(self, agent_id: int, inventory: dict[int, int]) -> None: ...
    def get_collective_inventories(self) -> dict[str, dict[str, int]]: ...
