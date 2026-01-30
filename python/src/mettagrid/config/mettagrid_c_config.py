from typing import Any

from mettagrid.config.game_value import Scope
from mettagrid.config.handler_config import AlignmentCondition
from mettagrid.config.mettagrid_c_mutations import convert_entity_ref, convert_mutations
from mettagrid.config.mettagrid_c_value_config import resolve_game_value
from mettagrid.config.mettagrid_config import (
    AgentConfig,
    AssemblerConfig,
    ChestConfig,
    GameConfig,
    GridObjectConfig,
    WallConfig,
)
from mettagrid.config.tag import typeTag
from mettagrid.mettagrid_c import ActionConfig as CppActionConfig
from mettagrid.mettagrid_c import AgentConfig as CppAgentConfig
from mettagrid.mettagrid_c import AlignmentCondition as CppAlignmentCondition
from mettagrid.mettagrid_c import AlignmentFilterConfig as CppAlignmentFilterConfig
from mettagrid.mettagrid_c import AlignmentMutationConfig as CppAlignmentMutationConfig
from mettagrid.mettagrid_c import AlignTo as CppAlignTo
from mettagrid.mettagrid_c import AOEConfig as CppAOEConfig
from mettagrid.mettagrid_c import AssemblerConfig as CppAssemblerConfig
from mettagrid.mettagrid_c import AttackActionConfig as CppAttackActionConfig
from mettagrid.mettagrid_c import AttackOutcome as CppAttackOutcome
from mettagrid.mettagrid_c import ChangeVibeActionConfig as CppChangeVibeActionConfig
from mettagrid.mettagrid_c import ChestConfig as CppChestConfig
from mettagrid.mettagrid_c import CollectiveConfig as CppCollectiveConfig
from mettagrid.mettagrid_c import EventConfig as CppEventConfig
from mettagrid.mettagrid_c import GameConfig as CppGameConfig
from mettagrid.mettagrid_c import GameValueFilterConfig as CppGameValueFilterConfig
from mettagrid.mettagrid_c import GlobalObsConfig as CppGlobalObsConfig
from mettagrid.mettagrid_c import GridObjectConfig as CppGridObjectConfig
from mettagrid.mettagrid_c import HandlerConfig as CppHandlerConfig
from mettagrid.mettagrid_c import InventoryConfig as CppInventoryConfig
from mettagrid.mettagrid_c import LimitDef as CppLimitDef
from mettagrid.mettagrid_c import MoveActionConfig as CppMoveActionConfig
from mettagrid.mettagrid_c import NearFilterConfig as CppNearFilterConfig
from mettagrid.mettagrid_c import ObsValueConfig as CppObsValueConfig
from mettagrid.mettagrid_c import Protocol as CppProtocol
from mettagrid.mettagrid_c import ResourceDelta as CppResourceDelta
from mettagrid.mettagrid_c import ResourceFilterConfig as CppResourceFilterConfig
from mettagrid.mettagrid_c import RewardConfig as CppRewardConfig
from mettagrid.mettagrid_c import RewardEntry as CppRewardEntry
from mettagrid.mettagrid_c import TagFilterConfig as CppTagFilterConfig
from mettagrid.mettagrid_c import TransferActionConfig as CppTransferActionConfig
from mettagrid.mettagrid_c import VibeFilterConfig as CppVibeFilterConfig
from mettagrid.mettagrid_c import VibeTransferEffect as CppVibeTransferEffect
from mettagrid.mettagrid_c import WallConfig as CppWallConfig


def _convert_alignment_condition(alignment) -> CppAlignmentCondition:
    """Convert Python AlignmentCondition to C++ AlignmentCondition enum."""
    mapping = {
        AlignmentCondition.ALIGNED: CppAlignmentCondition.aligned,
        AlignmentCondition.UNALIGNED: CppAlignmentCondition.unaligned,
        AlignmentCondition.SAME_COLLECTIVE: CppAlignmentCondition.same_collective,
        AlignmentCondition.DIFFERENT_COLLECTIVE: CppAlignmentCondition.different_collective,
    }
    return mapping.get(alignment, CppAlignmentCondition.same_collective)


def _scope_to_feature_str(scope: Scope) -> str:
    """Get the scope string for feature name construction."""
    return {Scope.AGENT: "own", Scope.GAME: "global", Scope.COLLECTIVE: "collective"}[scope]


def _resolve_near_tag_id(filter_config, tag_name_to_id: dict, context: str) -> int:
    """Resolve the tag_id for a NearFilter's target_tag.

    Args:
        filter_config: NearFilter config with target_tag attribute
        tag_name_to_id: Dict mapping tag names to IDs
        context: Description for error messages

    Returns:
        The tag_id for the target_tag

    Raises:
        ValueError: If target_tag is not found in tag_name_to_id
    """
    target_tag = filter_config.target_tag
    if target_tag not in tag_name_to_id:
        raise ValueError(
            f"NearFilter in {context} references unknown tag '{target_tag}'. Add it to GameConfig.tags or object tags."
        )
    return tag_name_to_id[target_tag]


def _convert_handlers(handlers_dict, resource_name_to_id, limit_name_to_resource_ids, vibe_name_to_id, tag_name_to_id):
    """Convert Python Handler dict to C++ HandlerConfig list.

    Args:
        handlers_dict: Dict mapping handler name to Handler config
        resource_name_to_id: Dict mapping resource names to IDs
        limit_name_to_resource_ids: Dict mapping limit names to lists of resource IDs
        vibe_name_to_id: Dict mapping vibe names to IDs
        tag_name_to_id: Dict mapping tag names to IDs

    Returns:
        List of CppHandlerConfig objects
    """
    cpp_handlers = []

    for handler_name, handler in handlers_dict.items():
        cpp_handler = CppHandlerConfig(handler_name)
        cpp_handler.radius = handler.radius

        _convert_filters(
            handler.filters,
            cpp_handler,
            resource_name_to_id,
            vibe_name_to_id,
            tag_name_to_id,
            context=f"handler '{handler_name}'",
        )

        convert_mutations(
            handler.mutations,
            cpp_handler,
            resource_name_to_id,
            limit_name_to_resource_ids,
            tag_name_to_id,
            context=f"handler '{handler_name}'",
        )

        cpp_handlers.append(cpp_handler)

    return cpp_handlers


def _convert_filters(filters, cpp_target, resource_name_to_id, vibe_name_to_id, tag_name_to_id, context: str = ""):
    """Convert Python filters to C++ and add them to the target config.

    Args:
        filters: List of filter configs
        cpp_target: Target object with add_*_filter methods
        resource_name_to_id: Dict mapping resource names to IDs
        vibe_name_to_id: Dict mapping vibe names to IDs
        tag_name_to_id: Dict mapping tag names to IDs
        context: Description for error messages (unused, kept for compatibility)
    """
    for filter_config in filters:
        filter_type = getattr(filter_config, "filter_type", None)

        if filter_type == "alignment":
            cpp_filter = CppAlignmentFilterConfig(
                condition=_convert_alignment_condition(filter_config.alignment),
            )
            cpp_target.add_alignment_filter(cpp_filter)

        elif filter_type == "resource":
            for resource_name, min_amount in filter_config.resources.items():
                if resource_name in resource_name_to_id:
                    cpp_filter = CppResourceFilterConfig(
                        entity=convert_entity_ref(filter_config.target),
                        resource_id=resource_name_to_id[resource_name],
                        min_amount=min_amount,
                    )
                    cpp_target.add_resource_filter(cpp_filter)

        elif filter_type == "vibe":
            if filter_config.vibe in vibe_name_to_id:
                cpp_filter = CppVibeFilterConfig(
                    entity=convert_entity_ref(filter_config.target),
                    vibe_id=vibe_name_to_id[filter_config.vibe],
                )
                cpp_target.add_vibe_filter(cpp_filter)

        elif filter_type == "tag":
            if filter_config.tag in tag_name_to_id:
                cpp_filter = CppTagFilterConfig(
                    entity=convert_entity_ref(filter_config.target),
                    tag_id=tag_name_to_id[filter_config.tag],
                )
                cpp_target.add_tag_filter(cpp_filter)

        elif filter_type == "near":
            # NearFilter requires a tag for efficient spatial lookup
            tag_id = _resolve_near_tag_id(filter_config, tag_name_to_id, "handler filters")
            cpp_filter = CppNearFilterConfig(
                entity=convert_entity_ref(filter_config.target),
                radius=filter_config.radius,
                target_tag=tag_id,
            )
            # Convert and add filters
            _add_filters_to_near_filter(
                filter_config.filters,
                cpp_filter,
                resource_name_to_id,
                vibe_name_to_id,
                tag_name_to_id,
            )
            cpp_target.add_near_filter(cpp_filter)

        elif filter_type == "game_value":
            from mettagrid.config.mettagrid_c_value_config import resolve_game_value

            mappings = {
                "resource_name_to_id": resource_name_to_id,
                "stat_name_to_id": {},  # Stat IDs resolved at C++ init time
                "tag_name_to_id": tag_name_to_id,
            }
            cpp_gv_cfg = resolve_game_value(filter_config.value, mappings)
            cpp_filter = CppGameValueFilterConfig(
                value=cpp_gv_cfg,
                threshold=float(filter_config.min),
                entity=convert_entity_ref(filter_config.target),
            )
            cpp_target.add_game_value_filter(cpp_filter)


def _add_filters_to_near_filter(
    filters, cpp_near_filter, resource_name_to_id, vibe_name_to_id, tag_name_to_id, collective_name_to_id=None
):
    """Add filters to a NearFilterConfig.

    Args:
        filters: List of Python filter configs
        cpp_near_filter: CppNearFilterConfig to add filters to
        resource_name_to_id: Dict mapping resource names to IDs
        vibe_name_to_id: Dict mapping vibe names to IDs
        tag_name_to_id: Dict mapping tag names to IDs
        collective_name_to_id: Dict mapping collective names to IDs (optional)
    """
    collective_name_to_id = collective_name_to_id or {}

    for filter_cfg in filters:
        filter_type = getattr(filter_cfg, "filter_type", None)

        if filter_type == "alignment":
            cpp_filter = CppAlignmentFilterConfig(
                condition=_convert_alignment_condition(filter_cfg.alignment),
            )
            # Set collective_id if specific collective is specified
            collective = getattr(filter_cfg, "collective", None)
            if collective is not None and collective in collective_name_to_id:
                cpp_filter.collective_id = collective_name_to_id[collective]
            cpp_near_filter.add_alignment_filter(cpp_filter)

        elif filter_type == "vibe":
            if filter_cfg.vibe in vibe_name_to_id:
                cpp_filter = CppVibeFilterConfig(
                    entity=convert_entity_ref(filter_cfg.target),
                    vibe_id=vibe_name_to_id[filter_cfg.vibe],
                )
                cpp_near_filter.add_vibe_filter(cpp_filter)

        elif filter_type == "resource":
            for resource_name, min_amount in filter_cfg.resources.items():
                if resource_name in resource_name_to_id:
                    cpp_filter = CppResourceFilterConfig(
                        entity=convert_entity_ref(filter_cfg.target),
                        resource_id=resource_name_to_id[resource_name],
                        min_amount=min_amount,
                    )
                    cpp_near_filter.add_resource_filter(cpp_filter)

        elif filter_type == "tag":
            if filter_cfg.tag in tag_name_to_id:
                cpp_filter = CppTagFilterConfig(
                    entity=convert_entity_ref(filter_cfg.target),
                    tag_id=tag_name_to_id[filter_cfg.tag],
                )
                cpp_near_filter.add_tag_filter(cpp_filter)


def _convert_event_configs(
    events: dict,
    resource_name_to_id: dict,
    limit_name_to_resource_ids: dict,
    vibe_name_to_id: dict,
    tag_name_to_id: dict,
    type_id_by_type_name: dict,
    collective_name_to_id: dict,
) -> dict:
    """Convert Python EventConfig dict to C++ EventConfig dict.

    Args:
        events: Dict mapping event name to EventConfig
        resource_name_to_id: Dict mapping resource names to IDs
        limit_name_to_resource_ids: Dict mapping limit names to lists of resource IDs
        vibe_name_to_id: Dict mapping vibe names to IDs
        tag_name_to_id: Dict mapping tag names to IDs
        type_id_by_type_name: Dict mapping object type names to type IDs
        collective_name_to_id: Dict mapping collective names to IDs

    Returns:
        Dict of event name -> CppEventConfig
    """
    cpp_events = {}

    for event_name, event in events.items():
        cpp_event = CppEventConfig(event.name)
        cpp_event.timesteps = list(event.timesteps)
        cpp_event.max_targets = event.max_targets if event.max_targets is not None else 0
        cpp_event.fallback = event.fallback or ""

        # Set target_tag_id for efficient target lookup via TagIndex
        if event.target_tag not in tag_name_to_id:
            raise ValueError(
                f"Event '{event_name}' has target_tag '{event.target_tag}' not found in tag mappings. "
                f"Available tags: {sorted(tag_name_to_id.keys())}"
            )
        cpp_event.target_tag_id = tag_name_to_id[event.target_tag]

        # Set target_tag_id for efficient target lookup via TagIndex
        if event.target_tag not in tag_name_to_id:
            raise ValueError(
                f"Event '{event_name}' has target_tag '{event.target_tag}' not found in tag mappings. "
                f"Available tags: {sorted(tag_name_to_id.keys())}"
            )
        cpp_event.target_tag_id = tag_name_to_id[event.target_tag]

        # Convert filters
        _convert_event_filters(
            event.filters,
            cpp_event,
            resource_name_to_id,
            vibe_name_to_id,
            tag_name_to_id,
            collective_name_to_id,
        )

        # Convert mutations using shared utility
        _convert_event_mutations(
            event.mutations,
            cpp_event,
            resource_name_to_id,
            limit_name_to_resource_ids,
            tag_name_to_id,
            collective_name_to_id,
            context=f"event '{event_name}'",
        )

        cpp_events[event_name] = cpp_event

    return cpp_events


def _convert_event_filters(
    filters,
    cpp_target,
    resource_name_to_id,
    vibe_name_to_id,
    tag_name_to_id,
    collective_name_to_id,
):
    """Convert Python filters for events.

    Uses standard filters: alignment, resource, vibe, tag, near.
    """
    for filter_config in filters:
        filter_type = getattr(filter_config, "filter_type", None)

        if filter_type == "alignment":
            cpp_filter = CppAlignmentFilterConfig()
            cpp_filter.condition = _convert_alignment_condition(filter_config.alignment)
            # If collective is specified, set the collective_id for specific collective matching
            collective = getattr(filter_config, "collective", None)
            if collective is not None and collective in collective_name_to_id:
                cpp_filter.collective_id = collective_name_to_id[collective]
            cpp_target.add_alignment_filter(cpp_filter)

        elif filter_type == "resource":
            # Resource filter can have multiple resources - add one filter per resource
            for resource_name, min_amount in filter_config.resources.items():
                if resource_name in resource_name_to_id:
                    cpp_filter = CppResourceFilterConfig()
                    cpp_filter.entity = convert_entity_ref(filter_config.target)
                    cpp_filter.resource_id = resource_name_to_id[resource_name]
                    cpp_filter.min_amount = min_amount
                    cpp_target.add_resource_filter(cpp_filter)

        elif filter_type == "vibe":
            if filter_config.vibe in vibe_name_to_id:
                cpp_filter = CppVibeFilterConfig()
                cpp_filter.entity = convert_entity_ref(filter_config.target)
                cpp_filter.vibe_id = vibe_name_to_id[filter_config.vibe]
                cpp_target.add_vibe_filter(cpp_filter)

        elif filter_type == "tag":
            if filter_config.tag in tag_name_to_id:
                cpp_filter = CppTagFilterConfig()
                cpp_filter.entity = convert_entity_ref(filter_config.target)
                cpp_filter.tag_id = tag_name_to_id[filter_config.tag]
                cpp_target.add_tag_filter(cpp_filter)

        elif filter_type == "near":
            # NearFilter requires a tag for efficient spatial lookup
            tag_id = _resolve_near_tag_id(filter_config, tag_name_to_id, "event filters")
            cpp_filter = CppNearFilterConfig()
            cpp_filter.entity = convert_entity_ref(filter_config.target)
            cpp_filter.radius = filter_config.radius
            cpp_filter.target_tag = tag_id
            # Convert and add filters
            _add_filters_to_near_filter(
                filter_config.filters,
                cpp_filter,
                resource_name_to_id,
                vibe_name_to_id,
                tag_name_to_id,
                collective_name_to_id,
            )
            cpp_target.add_near_filter(cpp_filter)


def _convert_event_mutations(
    mutations,
    cpp_target,
    resource_name_to_id,
    limit_name_to_resource_ids,
    tag_name_to_id,
    collective_name_to_id,
    context: str,
):
    """Convert Python mutations for events, including event-specific mutation types.

    Supports all standard mutations plus:
    - AlignmentMutation with collective set: Align entity to a specific collective by ID
    """
    from mettagrid.config.mettagrid_c_mutations import convert_mutations
    from mettagrid.config.mutation import AlignmentMutation

    # Separate out AlignmentMutation with collective set - these need special handling
    standard_mutations = []
    collective_alignment_mutations = []

    for mutation in mutations:
        if isinstance(mutation, AlignmentMutation) and mutation.collective is not None:
            collective_alignment_mutations.append(mutation)
        else:
            standard_mutations.append(mutation)

    # Convert standard mutations (excluding collective alignments)
    convert_mutations(
        standard_mutations,
        cpp_target,
        resource_name_to_id,
        limit_name_to_resource_ids,
        tag_name_to_id,
        context,
    )

    # Handle AlignmentMutation with collective set -> AlignmentMutationConfig with collective_id
    for mutation in collective_alignment_mutations:
        collective_name = mutation.collective
        if collective_name in collective_name_to_id:
            cpp_mut = CppAlignmentMutationConfig()
            cpp_mut.align_to = CppAlignTo.none  # Ignored when collective_id is set
            cpp_mut.collective_id = collective_name_to_id[collective_name]
            cpp_target.add_alignment_mutation(cpp_mut)
        else:
            raise ValueError(f"Collective '{collective_name}' not found in collective_name_to_id mapping in {context}")


def _convert_aoe_configs(
    aoes: dict,
    resource_name_to_id: dict,
    limit_name_to_resource_ids: dict,
    vibe_name_to_id: dict,
    tag_name_to_id: dict,
) -> list:
    """Convert Python AOEConfig dict to C++ AOEConfig list.

    Args:
        aoes: Dict of AOEConfig from Python (name -> config)
        resource_name_to_id: Dict mapping resource names to IDs
        limit_name_to_resource_ids: Dict mapping limit names to resource ID lists
        vibe_name_to_id: Dict mapping vibe names to IDs
        tag_name_to_id: Dict mapping tag names to IDs

    Returns:
        List of CppAOEConfig objects
    """
    cpp_aoe_configs = []

    for aoe in aoes.values():
        cpp_aoe = CppAOEConfig()
        cpp_aoe.radius = aoe.radius
        cpp_aoe.is_static = aoe.is_static
        cpp_aoe.effect_self = aoe.effect_self

        _convert_filters(
            aoe.filters,
            cpp_aoe,
            resource_name_to_id,
            vibe_name_to_id,
            tag_name_to_id,
            context="AOEConfig",
        )

        convert_mutations(
            aoe.mutations,
            cpp_aoe,
            resource_name_to_id,
            limit_name_to_resource_ids,
            tag_name_to_id,
            context="AOEConfig",
        )

        # Convert presence_deltas (one-time resource changes on enter/exit)
        # Note: pybind11 returns copies of lists, so we must assign a new list, not append
        presence_deltas_list = []
        for resource_name, delta in aoe.presence_deltas.items():
            if resource_name not in resource_name_to_id:
                raise ValueError(f"Unknown resource '{resource_name}' in AOEConfig presence_deltas")
            presence_deltas_list.append(CppResourceDelta(resource_name_to_id[resource_name], delta))
        cpp_aoe.presence_deltas = presence_deltas_list

        cpp_aoe_configs.append(cpp_aoe)

    return cpp_aoe_configs


def convert_to_cpp_game_config(mettagrid_config: dict | GameConfig):
    """Convert a GameConfig to a CppGameConfig."""
    if isinstance(mettagrid_config, GameConfig):
        # If it's already a GameConfig instance, use it directly
        game_config = mettagrid_config
    else:
        # If it's a dict, remove computed fields before instantiating GameConfig
        # features is a computed field and can't be set during __init__
        config_dict = mettagrid_config.copy()
        if "obs" in config_dict and "features" in config_dict["obs"]:
            config_dict["obs"] = config_dict["obs"].copy()
            config_dict["obs"].pop("features", None)
        # Keep vibe_names in sync with vibes; favor the vibes list.
        config_dict.pop("vibe_names", None)
        game_config = GameConfig(**config_dict)

    # Ensure runtime object has consistent vibes.
    game_config.vibe_names = [vibe.name for vibe in game_config.actions.change_vibe.vibes]

    # Set up resource mappings
    resource_names = list(game_config.resource_names)
    resource_name_to_id = {name: i for i, name in enumerate(resource_names)}

    # Compute deterministic type_id mapping for C++ (Python never exposes these)
    # Include agent names alongside object names - agents are treated like any other type
    type_names = set(game_config.objects.keys())
    for agent_config in game_config.agents:
        type_names.add(agent_config.name)
    if not game_config.agents and game_config.num_agents > 0:
        type_names.add(game_config.agent.name)
    type_names_sorted = sorted(type_names)
    type_id_by_type_name = {name: i for i, name in enumerate(type_names_sorted)}

    # Set up vibe mappings from the change_vibe action config.
    # The C++ bindings expect dense uint8 identifiers, so keep a name->id lookup.
    supported_vibes = game_config.actions.change_vibe.vibes
    vibe_name_to_id = {vibe.name: i for i, vibe in enumerate(supported_vibes)}

    # Build collective_name_to_id mapping (sorted for deterministic IDs matching C++)
    collective_name_to_id = {name: idx for idx, name in enumerate(sorted(game_config.collectives.keys()))}

    objects_cpp_params = {}  # params for CppWallConfig

    # These are the baseline settings for all agents
    default_agent_config_dict = game_config.agent.model_dump()
    default_resource_limit = default_agent_config_dict["inventory"]["default_limit"]

    # Build limit_name -> resource_ids mapping from default agent inventory config
    # This is used by ClearInventoryMutation to resolve limit names to resource IDs
    limit_name_to_resource_ids = {}
    default_agent_inv_config = default_agent_config_dict.get("inventory", {})
    for limit_name, limit_config in default_agent_inv_config.get("limits", {}).items():
        limit_resource_names = limit_config.get("resources", [])
        limit_resource_ids = [resource_name_to_id[name] for name in limit_resource_names if name in resource_name_to_id]
        limit_name_to_resource_ids[limit_name] = limit_resource_ids

    # If no agents specified, create default agents with appropriate team IDs
    if not game_config.agents:
        # Create default agents that inherit from game_config.agent
        base_agent_dict = game_config.agent.model_dump()
        game_config.agents = []
        for _ in range(game_config.num_agents):
            agent_dict = base_agent_dict.copy()
            agent_dict["team_id"] = 0  # All default agents are on team 0
            game_config.agents.append(AgentConfig(**agent_dict))

    # Build tag mappings - collect all unique tags from all objects
    # Note: This must happen AFTER default agents are created, so their tags are included
    # All tag references in handlers must refer to GameConfig.tags, obj.tags, or type:object_type
    all_tags = set(game_config.tags)
    for obj_name, obj_config in game_config.objects.items():
        all_tags.update(obj_config.tags)
        all_tags.add(typeTag(obj_name))

    # Collect tags from agents (created from default config if list was empty)
    for agent_config in game_config.agents:
        all_tags.update(agent_config.tags)
        all_tags.add(typeTag(agent_config.name))

    tag_id_offset = 0  # Start tag IDs at 0
    sorted_tags = sorted(all_tags)

    # Validate tag count doesn't exceed uint8 max (255)
    if len(sorted_tags) > 256:
        raise ValueError(f"Too many unique tags ({len(sorted_tags)}). Maximum supported is 256 due to uint8 limit.")

    tag_name_to_id: dict[str, int] = {str(tag): tag_id_offset + i for i, tag in enumerate(sorted_tags)}
    tag_id_to_name = {id: name for name, id in tag_name_to_id.items()}

    # Group agents by team_id to create groups
    team_groups = {}
    for agent_idx, agent_config in enumerate(game_config.agents):
        team_id = agent_config.team_id
        if team_id not in team_groups:
            team_groups[team_id] = []
        team_groups[team_id].append((agent_idx, agent_config))

    # Create a group for each team
    for team_id, team_agents in team_groups.items():
        # Use the first agent in the team as the template for the group
        _, first_agent = team_agents[0]
        agent_props = first_agent.model_dump()

        # Validate that all agents in the team have identical tags
        # Currently tags are applied per-team, not per-agent
        first_agent_tags = set(first_agent.tags)
        for agent_idx, agent_config in team_agents[1:]:
            if set(agent_config.tags) != first_agent_tags:
                raise ValueError(
                    f"All agents in team {team_id} must have identical tags. "
                    f"Agent 0 has tags {sorted(first_agent_tags)}, "
                    f"but agent {agent_idx} has tags {sorted(agent_config.tags)}. "
                    f"Tags are currently applied per-team, not per-agent."
                )

        # Convert rewards to RewardEntry list for C++ v2 pipeline
        mappings = {
            "resource_name_to_id": resource_name_to_id,
            "tag_name_to_id": tag_name_to_id,
        }
        reward_entries = []
        for reward_name, agent_reward in first_agent.rewards.items():
            entry = CppRewardEntry()
            if len(agent_reward.nums) != 1:
                raise ValueError(
                    f"Reward '{reward_name}' has {len(agent_reward.nums)} numerators, "
                    "but only a single numerator per reward is supported."
                )
            entry.numerator = resolve_game_value(agent_reward.nums[0], mappings)
            entry.denominators = [resolve_game_value(d, mappings) for d in agent_reward.denoms]
            entry.weight = agent_reward.weight
            if agent_reward.max is not None:
                entry.max_value = agent_reward.max
                entry.has_max = True
            reward_entries.append(entry)

        # Get inventory config
        inv_config = agent_props.get("inventory", {})

        # Process potential initial inventory
        initial_inventory = {resource_name_to_id[k]: v for k, v in inv_config.get("initial", {}).items()}

        # Map team IDs to conventional group names
        team_names = {0: "red", 1: "blue", 2: "green", 3: "yellow", 4: "purple", 5: "orange"}
        group_name = team_names.get(team_id, f"team_{team_id}")
        # Convert tag names to IDs for first agent in team (include auto-generated type tag)
        agent_tags = list(first_agent.tags) + [typeTag(first_agent.name)]
        tag_ids = [tag_name_to_id[tag] for tag in agent_tags]

        # Build inventory config with support for grouped limits and modifiers
        limit_defs = []

        # First, handle explicitly configured limits (both individual and grouped)
        configured_resources = set()
        for resource_limit in inv_config.get("limits", {}).values():
            # Convert resource names to IDs
            resource_ids = [resource_name_to_id[name] for name in resource_limit["resources"]]
            # Convert modifier names to IDs
            modifiers_dict = resource_limit.get("modifiers", {})
            modifier_ids = {
                resource_name_to_id[name]: bonus
                for name, bonus in modifiers_dict.items()
                if name in resource_name_to_id
            }
            min_val = resource_limit.get("min", resource_limit.get("limit", 0))
            max_val = resource_limit.get("max", 65535)
            limit_defs.append(CppLimitDef(resource_ids, min_val, max_val, modifier_ids))
            configured_resources.update(resource_limit["resources"])

        # Add default limits for unconfigured resources
        for resource_name in resource_names:
            if resource_name not in configured_resources:
                limit_defs.append(CppLimitDef([resource_name_to_id[resource_name]], default_resource_limit))

        inventory_config = CppInventoryConfig()
        inventory_config.limit_defs = limit_defs

        reward_config = CppRewardConfig()
        reward_config.entries = reward_entries

        cpp_agent_config = CppAgentConfig(
            type_id=type_id_by_type_name[first_agent.name],
            type_name=first_agent.name,
            group_id=team_id,
            group_name=group_name,
            freeze_duration=agent_props["freeze_duration"],
            initial_vibe=agent_props["vibe"],
            inventory_config=inventory_config,
            reward_config=reward_config,
            initial_inventory=initial_inventory,
        )
        cpp_agent_config.tag_ids = tag_ids

        # Set collective_id if agent belongs to a collective
        if first_agent.collective and first_agent.collective in collective_name_to_id:
            cpp_agent_config.collective_id = collective_name_to_id[first_agent.collective]

        # Convert agent aoes (dict[str, AOEConfig]) to C++ AOEConfig list
        if first_agent.aoes:
            cpp_agent_config.aoe_configs = _convert_aoe_configs(
                first_agent.aoes,
                resource_name_to_id,
                limit_name_to_resource_ids,
                vibe_name_to_id,
                tag_name_to_id,
            )

        # Convert agent on_tick (dict[str, Handler]) to C++ HandlerConfig list
        if first_agent.on_tick:
            cpp_agent_config.on_tick = _convert_handlers(
                first_agent.on_tick,
                resource_name_to_id,
                limit_name_to_resource_ids,
                vibe_name_to_id,
                tag_name_to_id,
            )

        objects_cpp_params["agent." + group_name] = cpp_agent_config

        # Also register team_X naming convention for maps that use it
        objects_cpp_params[f"agent.team_{team_id}"] = cpp_agent_config

        # Also register aliases for team 0 for backward compatibility
        if team_id == 0:
            objects_cpp_params["agent.default"] = cpp_agent_config
            objects_cpp_params["agent.agent"] = cpp_agent_config

    # Convert other objects
    for object_type, object_config in game_config.objects.items():
        cpp_config = None  # Will hold the created C++ config object

        # Common GridObjectConfig fields - computed once (include auto-generated type tag)
        type_id = type_id_by_type_name[object_type]
        object_tags = list(object_config.tags) + [typeTag(object_type)]
        tag_ids = [tag_name_to_id[tag] for tag in object_tags]

        if isinstance(object_config, WallConfig):
            cpp_config = CppWallConfig(type_id=type_id, type_name=object_type, initial_vibe=object_config.vibe)
        elif isinstance(object_config, AssemblerConfig):
            protocols = []
            seen_vibes_and_min_agents = []

            for protocol_config in reversed(object_config.protocols):
                # Convert vibe names to IDs (validate all vibe names exist)
                for vibe in protocol_config.vibes:
                    if vibe not in vibe_name_to_id:
                        raise ValueError(f"Unknown vibe name '{vibe}' in assembler '{object_type}' protocol")
                vibe_ids = sorted([vibe_name_to_id[vibe] for vibe in protocol_config.vibes])
                # Check for duplicate vibes
                if (vibe_ids, protocol_config.min_agents) in seen_vibes_and_min_agents:
                    raise ValueError(
                        f"Protocol with vibes {protocol_config.vibes} and min_agents {protocol_config.min_agents} "
                        f"already exists in {object_type}"
                    )
                seen_vibes_and_min_agents.append((vibe_ids, protocol_config.min_agents))
                # Ensure keys and values are explicitly Python ints for C++ binding
                # Build dict item-by-item to ensure pybind11 recognizes it as dict[int, int]
                input_res = {}
                for k, v in protocol_config.input_resources.items():
                    key = int(resource_name_to_id[k])
                    val = int(v)
                    input_res[key] = val
                output_res = {}
                for k, v in protocol_config.output_resources.items():
                    key = int(resource_name_to_id[k])
                    val = int(v)
                    output_res[key] = val
                cpp_protocol = CppProtocol()
                cpp_protocol.min_agents = protocol_config.min_agents
                cpp_protocol.vibes = vibe_ids
                cpp_protocol.input_resources = input_res
                cpp_protocol.output_resources = output_res
                cpp_protocol.cooldown = protocol_config.cooldown
                protocols.append(cpp_protocol)

            cpp_config = CppAssemblerConfig(type_id=type_id, type_name=object_type, initial_vibe=object_config.vibe)
            cpp_config.protocols = protocols
            cpp_config.allow_partial_usage = object_config.allow_partial_usage
            cpp_config.max_uses = object_config.max_uses
            cpp_config.chest_search_distance = object_config.chest_search_distance
        elif isinstance(object_config, ChestConfig):
            # Convert vibe_transfers: vibe -> resource -> delta
            vibe_transfers_map = {}
            for vibe_name, resource_deltas in object_config.vibe_transfers.items():
                if vibe_name not in vibe_name_to_id:
                    raise ValueError(f"Unknown vibe name '{vibe_name}' in chest '{object_type}' vibe_transfers")
                vibe_id = vibe_name_to_id[vibe_name]
                resource_deltas_cpp = {
                    resource_name_to_id[resource]: delta for resource, delta in resource_deltas.items()
                }
                vibe_transfers_map[vibe_id] = resource_deltas_cpp

            # Convert initial inventory from nested inventory config
            initial_inventory_cpp = {}
            for resource, amount in object_config.inventory.initial.items():
                resource_id = resource_name_to_id[resource]
                initial_inventory_cpp[resource_id] = amount

            # Create inventory config with limits and modifiers
            limit_defs = []
            for resource_limit in object_config.inventory.limits.values():
                # resources is always a list of strings
                resource_list = resource_limit.resources

                # Convert resource names to IDs
                resource_ids = [resource_name_to_id[name] for name in resource_list if name in resource_name_to_id]
                if resource_ids:
                    # Convert modifier names to IDs
                    modifier_ids = {
                        resource_name_to_id[name]: bonus
                        for name, bonus in resource_limit.modifiers.items()
                        if name in resource_name_to_id
                    }
                    limit_defs.append(CppLimitDef(resource_ids, resource_limit.min, resource_limit.max, modifier_ids))

            inventory_config = CppInventoryConfig()
            inventory_config.limit_defs = limit_defs

            cpp_config = CppChestConfig(type_id=type_id, type_name=object_type, initial_vibe=object_config.vibe)
            cpp_config.vibe_transfers = vibe_transfers_map
            cpp_config.initial_inventory = initial_inventory_cpp
            cpp_config.inventory_config = inventory_config
        elif isinstance(object_config, GridObjectConfig):
            # Handle base GridObjectConfig as a static object (like a wall with AOEs)
            cpp_config = CppGridObjectConfig(type_id=type_id, type_name=object_type, initial_vibe=object_config.vibe)
        else:
            raise ValueError(f"Unknown object type: {object_type}")

        # Set common GridObjectConfig fields generically
        if cpp_config is not None:
            cpp_config.tag_ids = tag_ids

            # Set collective_id if object belongs to a collective
            if object_config.collective and object_config.collective in collective_name_to_id:
                cpp_config.collective_id = collective_name_to_id[object_config.collective]

            # Convert the three handler types
            if object_config.on_use_handlers:
                cpp_config.on_use_handlers = _convert_handlers(
                    object_config.on_use_handlers,
                    resource_name_to_id,
                    limit_name_to_resource_ids,
                    vibe_name_to_id,
                    tag_name_to_id,
                )
            # Convert aoes (dict[str, AOEConfig]) to C++ AOEConfig list
            if object_config.aoes:
                cpp_config.aoe_configs = _convert_aoe_configs(
                    object_config.aoes,
                    resource_name_to_id,
                    limit_name_to_resource_ids,
                    vibe_name_to_id,
                    tag_name_to_id,
                )

            # Key by map_name so map grid (which uses map_name) resolves directly.
            objects_cpp_params[object_config.map_name or object_type] = cpp_config

    game_cpp_params = game_config.model_dump(exclude_none=True)
    del game_cpp_params["agent"]
    if "agents" in game_cpp_params:
        del game_cpp_params["agents"]
    if "params" in game_cpp_params:
        del game_cpp_params["params"]
    if "map_builder" in game_cpp_params:
        del game_cpp_params["map_builder"]
    if "tags" in game_cpp_params:
        del game_cpp_params["tags"]

    # Extract obs config to top level for C++ compatibility
    if "obs" in game_cpp_params:
        obs_config = game_cpp_params.pop("obs")
        game_cpp_params["obs_width"] = obs_config["width"]
        game_cpp_params["obs_height"] = obs_config["height"]
        game_cpp_params["num_observation_tokens"] = obs_config["num_tokens"]
        game_cpp_params["token_value_base"] = obs_config.get("token_value_base", 256)
        # Note: token_dim is not used by C++ GameConfig, it's only used in Python

    # Convert observation features from Python to C++
    # Use id_map to get feature_ids
    id_map = game_config.id_map()
    game_cpp_params["feature_ids"] = {feature.name: feature.id for feature in id_map.features()}

    # Convert global_obs configuration
    global_obs_config = game_config.obs.global_obs

    # Convert obs with pre-computed feature IDs using GameValueConfig
    from mettagrid.config.game_value import InventoryValue, StatValue

    resource_name_to_id = {name: idx for idx, name in enumerate(game_config.resource_names)}
    mappings = {"resource_name_to_id": resource_name_to_id, "tag_name_to_id": tag_name_to_id}

    obs_cpp = []
    for game_value in global_obs_config.obs:
        cpp_obs = CppObsValueConfig()
        cpp_obs.value = resolve_game_value(game_value, mappings)
        # Compute feature name for ID lookup
        if isinstance(game_value, StatValue):
            feature_name = f"stat:{_scope_to_feature_str(game_value.scope)}:{game_value.name}"
            if game_value.delta:
                feature_name += ":delta"
        elif isinstance(game_value, InventoryValue):
            feature_name = f"inv:{_scope_to_feature_str(game_value.scope)}:{game_value.item}"
        else:
            raise ValueError(f"Unsupported GameValue type for obs: {type(game_value)}")
        cpp_obs.feature_id = game_cpp_params["feature_ids"][feature_name]
        obs_cpp.append(cpp_obs)

    global_obs_cpp = CppGlobalObsConfig(
        episode_completion_pct=global_obs_config.episode_completion_pct,
        last_action=global_obs_config.last_action,
        last_reward=global_obs_config.last_reward,
        compass=global_obs_config.compass,
        goal_obs=global_obs_config.goal_obs,
        local_position=global_obs_config.local_position,
        obs=obs_cpp,
    )
    game_cpp_params["global_obs"] = global_obs_cpp

    # Process actions using new typed config structure
    actions_config = game_config.actions
    actions_cpp_params = {}

    # Helper function to process common action config fields
    def process_action_config(action_name: str, action_config) -> dict[str, Any]:
        # If disabled, return empty config (C++ code checks enabled status)
        if not action_config.enabled:
            return {
                "consumed_resources": {},
                "required_resources": {},
            }

        # Only validate resources for enabled actions
        # Check if any consumed resources are not in resource_names
        missing_consumed = []
        for resource in action_config.consumed_resources.keys():
            if resource not in resource_name_to_id:
                missing_consumed.append(resource)

        if missing_consumed:
            raise ValueError(
                f"Action '{action_name}' has consumed_resources {missing_consumed} that are not in "
                f"resource_names. These resources will be ignored, making the action free! "
                f"Either add these resources to resource_names or disable the action."
            )

        consumed_resources = {resource_name_to_id[k]: int(v) for k, v in action_config.consumed_resources.items()}

        required_source = action_config.required_resources
        if not required_source:
            required_source = action_config.consumed_resources

        required_resources = {resource_name_to_id[k]: int(v) for k, v in required_source.items()}

        return {
            "consumed_resources": consumed_resources,
            "required_resources": required_resources,
        }

    # Process noop - always add to map
    action_params = process_action_config("noop", actions_config.noop)
    actions_cpp_params["noop"] = CppActionConfig(**action_params)

    # Process move - always add to map
    action_params = process_action_config("move", actions_config.move)
    action_params["allowed_directions"] = actions_config.move.allowed_directions
    actions_cpp_params["move"] = CppMoveActionConfig(**action_params)

    # Process attack - always add to map
    action_params = process_action_config("attack", actions_config.attack)
    attack_cfg = actions_config.attack
    # Always convert full attack config (enabled only controls standalone actions, not vibe-triggered)
    action_params["defense_resources"] = {resource_name_to_id[k]: v for k, v in attack_cfg.defense_resources.items()}
    action_params["armor_resources"] = {resource_name_to_id[k]: v for k, v in attack_cfg.armor_resources.items()}
    action_params["weapon_resources"] = {resource_name_to_id[k]: v for k, v in attack_cfg.weapon_resources.items()}
    # Convert success outcome
    success_actor = {resource_name_to_id[k]: v for k, v in attack_cfg.success.actor_inv_delta.items()}
    success_target = {resource_name_to_id[k]: v for k, v in attack_cfg.success.target_inv_delta.items()}
    success_loot = [resource_name_to_id[name] for name in attack_cfg.success.loot]
    action_params["success"] = CppAttackOutcome(
        success_actor,
        success_target,
        success_loot,
        attack_cfg.success.freeze,
    )
    action_params["enabled"] = attack_cfg.enabled
    # Convert vibes from names to IDs (validate all vibe names exist)
    for vibe in attack_cfg.vibes:
        if vibe not in vibe_name_to_id:
            raise ValueError(f"Unknown vibe name '{vibe}' in attack.vibes")
    action_params["vibes"] = [vibe_name_to_id[vibe] for vibe in attack_cfg.vibes]
    # Convert vibe_bonus from names to IDs
    for vibe in attack_cfg.vibe_bonus:
        if vibe not in vibe_name_to_id:
            raise ValueError(f"Unknown vibe name '{vibe}' in attack.vibe_bonus")
    action_params["vibe_bonus"] = {vibe_name_to_id[vibe]: bonus for vibe, bonus in attack_cfg.vibe_bonus.items()}
    actions_cpp_params["attack"] = CppAttackActionConfig(**action_params)

    # Process transfer - vibes are derived from vibe_transfers keys in C++
    transfer_cfg = actions_config.transfer
    vibe_transfers_cpp = {}
    seen_vibes: set[str] = set()
    for vt in transfer_cfg.vibe_transfers:
        if vt.vibe not in vibe_name_to_id:
            raise ValueError(f"Unknown vibe name '{vt.vibe}' in transfer.vibe_transfers")
        if vt.vibe in seen_vibes:
            raise ValueError(f"Duplicate vibe name '{vt.vibe}' in transfer.vibe_transfers")
        seen_vibes.add(vt.vibe)
        vibe_id = vibe_name_to_id[vt.vibe]
        target_deltas = {resource_name_to_id[k]: v for k, v in vt.target.items()}
        actor_deltas = {resource_name_to_id[k]: v for k, v in vt.actor.items()}
        vibe_transfers_cpp[vibe_id] = CppVibeTransferEffect(target_deltas, actor_deltas)
    actions_cpp_params["transfer"] = CppTransferActionConfig(
        required_resources={resource_name_to_id[k]: int(v) for k, v in transfer_cfg.required_resources.items()},
        vibe_transfers=vibe_transfers_cpp,
        enabled=transfer_cfg.enabled,
    )

    # Process change_vibe - always add to map
    action_params = process_action_config("change_vibe", actions_config.change_vibe)
    num_vibes = len(actions_config.change_vibe.vibes) if actions_config.change_vibe.enabled else 0
    action_params["number_of_vibes"] = num_vibes
    actions_cpp_params["change_vibe"] = CppChangeVibeActionConfig(**action_params)

    game_cpp_params["actions"] = actions_cpp_params
    game_cpp_params["objects"] = objects_cpp_params

    # Add tag mappings for C++ debugging/display
    game_cpp_params["tag_id_map"] = tag_id_to_name

    # Convert collective configurations
    collectives_cpp = {}
    for collective_name, collective_cfg in game_config.collectives.items():
        # Build inventory config with limits
        limit_defs = []
        for resource_limit in collective_cfg.inventory.limits.values():
            resource_list = resource_limit.resources
            resource_ids = [resource_name_to_id[name] for name in resource_list if name in resource_name_to_id]
            if resource_ids:
                modifier_ids = {
                    resource_name_to_id[name]: bonus
                    for name, bonus in resource_limit.modifiers.items()
                    if name in resource_name_to_id
                }
                limit_defs.append(CppLimitDef(resource_ids, resource_limit.min, resource_limit.max, modifier_ids))

        inventory_config = CppInventoryConfig()
        inventory_config.limit_defs = limit_defs

        # Convert initial inventory
        initial_inventory_cpp = {}
        for resource, amount in collective_cfg.inventory.initial.items():
            if resource in resource_name_to_id:
                resource_id = resource_name_to_id[resource]
                initial_inventory_cpp[resource_id] = amount

        cpp_collective_config = CppCollectiveConfig(collective_name)
        cpp_collective_config.inventory_config = inventory_config
        cpp_collective_config.initial_inventory = initial_inventory_cpp
        collectives_cpp[collective_name] = cpp_collective_config

    game_cpp_params["collectives"] = collectives_cpp

    # Convert event configurations
    if game_config.events:
        events_cpp = _convert_event_configs(
            game_config.events,
            resource_name_to_id,
            limit_name_to_resource_ids,
            vibe_name_to_id,
            tag_name_to_id,
            type_id_by_type_name,
            collective_name_to_id,
        )
        game_cpp_params["events"] = events_cpp

    return CppGameConfig(**game_cpp_params)
