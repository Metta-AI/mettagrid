from typing import Any

from mettagrid.config.cpp_id_maps import CppIdMaps
from mettagrid.config.game_value import Scope
from mettagrid.config.handler_config import AlignmentCondition
from mettagrid.config.mettagrid_c_mutations import convert_entity_ref, convert_mutations
from mettagrid.config.mettagrid_c_value_config import resolve_game_value
from mettagrid.config.mettagrid_config import (
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
from mettagrid.mettagrid_c import AttackActionConfig as CppAttackActionConfig
from mettagrid.mettagrid_c import AttackOutcome as CppAttackOutcome
from mettagrid.mettagrid_c import ChangeVibeActionConfig as CppChangeVibeActionConfig
from mettagrid.mettagrid_c import CollectiveConfig as CppCollectiveConfig
from mettagrid.mettagrid_c import EventConfig as CppEventConfig
from mettagrid.mettagrid_c import GameConfig as CppGameConfig
from mettagrid.mettagrid_c import GameValueFilterConfig as CppGameValueFilterConfig
from mettagrid.mettagrid_c import GlobalObsConfig as CppGlobalObsConfig
from mettagrid.mettagrid_c import GridObjectConfig as CppGridObjectConfig
from mettagrid.mettagrid_c import Handler as CppHandler
from mettagrid.mettagrid_c import HandlerConfig as CppHandlerConfig
from mettagrid.mettagrid_c import HandlerMode as CppHandlerMode
from mettagrid.mettagrid_c import InventoryConfig as CppInventoryConfig
from mettagrid.mettagrid_c import LimitDef as CppLimitDef
from mettagrid.mettagrid_c import LogSumStatConfig as CppLogSumStatConfig
from mettagrid.mettagrid_c import MaxDistanceFilterConfig as CppMaxDistanceFilterConfig
from mettagrid.mettagrid_c import MoveActionConfig as CppMoveActionConfig
from mettagrid.mettagrid_c import MultiHandler as CppMultiHandler
from mettagrid.mettagrid_c import NegFilterConfig as CppNegFilterConfig
from mettagrid.mettagrid_c import ObsValueConfig as CppObsValueConfig
from mettagrid.mettagrid_c import OrFilterConfig as CppOrFilterConfig  # pyright: ignore[reportAttributeAccessIssue]
from mettagrid.mettagrid_c import ResourceDelta as CppResourceDelta
from mettagrid.mettagrid_c import ResourceFilterConfig as CppResourceFilterConfig
from mettagrid.mettagrid_c import RewardConfig as CppRewardConfig
from mettagrid.mettagrid_c import RewardEntry as CppRewardEntry
from mettagrid.mettagrid_c import (
    SharedTagPrefixFilterConfig as CppSharedTagPrefixFilterConfig,  # pyright: ignore[reportAttributeAccessIssue]
)
from mettagrid.mettagrid_c import TagPrefixFilterConfig as CppTagPrefixFilterConfig
from mettagrid.mettagrid_c import TagQueryConfig as CppTagQueryConfig
from mettagrid.mettagrid_c import VibeFilterConfig as CppVibeFilterConfig
from mettagrid.mettagrid_c import WallConfig as CppWallConfig
from mettagrid.mettagrid_c import make_query_config

# ---------------------------------------------------------------------------
# Enum conversion helpers
# ---------------------------------------------------------------------------

_ALIGNMENT_CONDITION_TO_CPP = {
    AlignmentCondition.ALIGNED: CppAlignmentCondition.aligned,
    AlignmentCondition.UNALIGNED: CppAlignmentCondition.unaligned,
    AlignmentCondition.SAME_COLLECTIVE: CppAlignmentCondition.same_collective,
    AlignmentCondition.DIFFERENT_COLLECTIVE: CppAlignmentCondition.different_collective,
}


def _scope_to_feature_str(scope: Scope) -> str:
    return {Scope.AGENT: "own", Scope.GAME: "global", Scope.COLLECTIVE: "collective"}[scope]


def _resolve_tag_prefix(prefix: str, tag_name_to_id: dict) -> list[int]:
    full_prefix = prefix + ":"
    return [tag_id for tag_name, tag_id in tag_name_to_id.items() if tag_name.startswith(full_prefix)]


# ---------------------------------------------------------------------------
# Tag query conversion (shared by proximity filters and mutation queries)
# ---------------------------------------------------------------------------


def _convert_tag_query(query, id_maps: CppIdMaps, context: str = ""):
    """Convert a Python Query to a C++ QueryConfig (wrapped in shared_ptr).

    Used by both MaxDistanceFilter (proximity) and QueryInventoryMutation.
    """
    query_tag = query.tag.name
    if query_tag not in id_maps.tag_name_to_id:
        raise ValueError(
            f"Tag query in {context} references unknown tag '{query_tag}'. Add it to GameConfig.tags or object tags."
        )

    tag_query = CppTagQueryConfig()
    tag_query.tag_id = id_maps.tag_name_to_id[query_tag]

    _convert_filters(query.filters, tag_query, id_maps, context=context)

    return make_query_config(tag_query)


# ---------------------------------------------------------------------------
# Single-filter conversion (the one place each filter type is handled)
# ---------------------------------------------------------------------------


def _convert_one_filter(filter_config, id_maps: CppIdMaps, context: str) -> tuple[str, object] | None:
    """Convert a single Python filter to (type_key, cpp_filter_or_list).

    Returns None if the filter should be silently skipped (unknown vibe/tag).
    For resource filters, result is a list (one CppResourceFilterConfig per resource).
    For not/or, result is CppNegFilterConfig/CppOrFilterConfig (fully built).
    """
    ft = getattr(filter_config, "filter_type", None)

    if ft == "not":
        return ("neg", _build_neg_filter(filter_config, id_maps, context))

    if ft == "or":
        return ("or", _build_or_filter(filter_config, id_maps, context))

    if ft == "alignment":
        cpp_filter = CppAlignmentFilterConfig(
            condition=_ALIGNMENT_CONDITION_TO_CPP.get(filter_config.alignment, CppAlignmentCondition.same_collective),
        )
        collective = getattr(filter_config, "collective", None)
        if collective is not None:
            if not id_maps.collective_name_to_id or collective not in id_maps.collective_name_to_id:
                available = sorted(id_maps.collective_name_to_id.keys()) if id_maps.collective_name_to_id else []
                raise ValueError(
                    f"AlignmentFilter references unknown collective '{collective}'. Available collectives: {available}"
                )
            cpp_filter.collective_id = id_maps.collective_name_to_id[collective]
        return ("alignment", cpp_filter)

    if ft == "resource":
        filters = []
        for resource_name, min_amount in filter_config.resources.items():
            if resource_name in id_maps.resource_name_to_id:
                filters.append(
                    CppResourceFilterConfig(
                        entity=convert_entity_ref(filter_config.target),
                        resource_id=id_maps.resource_name_to_id[resource_name],
                        min_amount=min_amount,
                    )
                )
        return ("resource", filters) if filters else None

    if ft == "vibe":
        if filter_config.vibe not in id_maps.vibe_name_to_id:
            return None
        return (
            "vibe",
            CppVibeFilterConfig(
                entity=convert_entity_ref(filter_config.target),
                vibe_id=id_maps.vibe_name_to_id[filter_config.vibe],
            ),
        )

    if ft == "tag":
        if filter_config.tag.name not in id_maps.tag_name_to_id:
            return None
        return (
            "tag_prefix",
            CppTagPrefixFilterConfig(
                entity=convert_entity_ref(filter_config.target),
                tag_ids=[id_maps.tag_name_to_id[filter_config.tag.name]],
            ),
        )

    if ft == "shared_tag_prefix":
        tag_ids = _resolve_tag_prefix(filter_config.tag_prefix, id_maps.tag_name_to_id)
        if not tag_ids:
            raise ValueError(
                f"SharedTagPrefixFilter prefix '{filter_config.tag_prefix}' matched no tags. "
                f"Available tags: {sorted(id_maps.tag_name_to_id.keys())}"
            )
        return ("shared_tag_prefix", CppSharedTagPrefixFilterConfig(tag_ids=tag_ids))

    if ft == "max_distance":
        source = _convert_tag_query(
            filter_config.query,
            id_maps,
            context=f"{context} max_distance source" if context else "max_distance source",
        )
        cpp_filter = CppMaxDistanceFilterConfig()
        cpp_filter.entity = convert_entity_ref(filter_config.target)
        cpp_filter.radius = filter_config.radius
        cpp_filter.set_source(source)
        return ("max_distance", cpp_filter)

    if ft == "game_value":
        cpp_gv_cfg = resolve_game_value(filter_config.value, id_maps)
        return (
            "game_value",
            CppGameValueFilterConfig(
                value=cpp_gv_cfg,
                threshold=float(filter_config.min),
                entity=convert_entity_ref(filter_config.target),
            ),
        )

    return None


# ---------------------------------------------------------------------------
# Filter attachment: all C++ targets use add_<type>_filter
# ---------------------------------------------------------------------------

_FILTER_TYPE_TO_METHOD = {
    "alignment": "add_alignment_filter",
    "resource": "add_resource_filter",
    "vibe": "add_vibe_filter",
    "tag_prefix": "add_tag_prefix_filter",
    "shared_tag_prefix": "add_shared_tag_prefix_filter",
    "max_distance": "add_max_distance_filter",
    "game_value": "add_game_value_filter",
    "neg": "add_neg_filter",
    "or": "add_or_filter",
}


def _attach(target, type_key: str, result):
    """Attach converted filter(s) to a C++ target."""
    method = getattr(target, _FILTER_TYPE_TO_METHOD[type_key])
    if isinstance(result, list):
        for item in result:
            method(item)
    else:
        method(result)


# ---------------------------------------------------------------------------
# Filter conversion: the three public entry points
# ---------------------------------------------------------------------------


def _convert_filters(filters, cpp_target, id_maps: CppIdMaps, context: str = ""):
    """Convert Python filters to C++ and add them to the target config."""
    for f in filters:
        converted = _convert_one_filter(f, id_maps, context)
        if converted is not None:
            _attach(cpp_target, *converted)


def _build_neg_filter(filter_config, id_maps: CppIdMaps, context: str) -> CppNegFilterConfig:
    """Convert a NotFilter to CppNegFilterConfig."""
    cpp_neg = CppNegFilterConfig()
    converted = _convert_one_filter(filter_config.inner, id_maps, context)
    if converted is not None:
        _attach(cpp_neg, *converted)
    return cpp_neg


def _build_or_filter(filter_config, id_maps: CppIdMaps, context: str) -> CppOrFilterConfig:
    """Convert an OrFilter to CppOrFilterConfig."""
    cpp_or = CppOrFilterConfig()
    for inner in filter_config.inner:
        converted = _convert_one_filter(inner, id_maps, context)
        if converted is None:
            continue
        type_key, result = converted
        # Multi-resource inside OR needs AND semantics: wrap in double negation
        if type_key == "resource" and isinstance(result, list) and len(result) > 1:
            inner_neg = CppNegFilterConfig()
            for r in result:
                inner_neg.add_resource_filter(r)
            outer_neg = CppNegFilterConfig()
            outer_neg.add_neg_filter(inner_neg)
            cpp_or.add_neg_filter(outer_neg)
        else:
            _attach(cpp_or, type_key, result)
    return cpp_or


# ---------------------------------------------------------------------------
# Handler / Event / AOE conversion
# ---------------------------------------------------------------------------


def _convert_handlers(handlers_dict, id_maps: CppIdMaps):
    """Convert Python Handler dict to C++ HandlerConfig list."""
    cpp_handlers = []
    for handler_name, handler in handlers_dict.items():
        cpp_handler = CppHandlerConfig(handler_name)
        _convert_filters(handler.filters, cpp_handler, id_maps, context=f"handler '{handler_name}'")
        convert_mutations(handler.mutations, cpp_handler, id_maps, context=f"handler '{handler_name}'")
        cpp_handlers.append(cpp_handler)
    return cpp_handlers


def _create_on_use_handler(handlers_dict, id_maps: CppIdMaps):
    """Create a single Handler (or MultiHandler) from Python Handler dict."""
    if not handlers_dict:
        return None
    handler_configs = _convert_handlers(handlers_dict, id_maps)
    handlers = [CppHandler(config) for config in handler_configs]
    return CppMultiHandler(handlers, CppHandlerMode.FirstMatch)


def _convert_event_configs(events: dict, id_maps: CppIdMaps) -> dict:
    """Convert Python EventConfig dict to C++ EventConfig dict."""
    cpp_events = {}
    for event_name, event in events.items():
        cpp_event = CppEventConfig(event.name)
        cpp_event.timesteps = list(event.timesteps)
        cpp_event.max_targets = event.max_targets if event.max_targets is not None else 0
        cpp_event.fallback = event.fallback or ""

        target_tag_name = event.target_query.tag.name
        if target_tag_name not in id_maps.tag_name_to_id:
            raise ValueError(
                f"Event '{event_name}' has target_query tag '{target_tag_name}' not found in tag mappings. "
                f"Available tags: {sorted(id_maps.tag_name_to_id.keys())}"
            )
        cpp_event.target_tag_id = id_maps.tag_name_to_id[target_tag_name]

        _convert_filters(event.filters, cpp_event, id_maps, context=f"event '{event_name}'")
        _convert_event_mutations(event.mutations, cpp_event, id_maps, context=f"event '{event_name}'")

        cpp_events[event_name] = cpp_event
    return cpp_events


def _convert_event_mutations(mutations, cpp_target, id_maps: CppIdMaps, context: str):
    """Convert Python mutations for events, including AlignmentMutation with collective."""
    from mettagrid.config.mutation import AlignmentMutation  # noqa: PLC0415

    standard_mutations = []
    collective_alignment_mutations = []
    for mutation in mutations:
        if isinstance(mutation, AlignmentMutation) and mutation.collective is not None:
            collective_alignment_mutations.append(mutation)
        else:
            standard_mutations.append(mutation)

    convert_mutations(standard_mutations, cpp_target, id_maps, context)

    for mutation in collective_alignment_mutations:
        collective_name = mutation.collective
        if collective_name in id_maps.collective_name_to_id:
            cpp_mut = CppAlignmentMutationConfig()
            cpp_mut.align_to = CppAlignTo.none
            cpp_mut.collective_id = id_maps.collective_name_to_id[collective_name]
            cpp_target.add_alignment_mutation(cpp_mut)
        else:
            raise ValueError(f"Collective '{collective_name}' not found in collective_name_to_id mapping in {context}")


def _convert_aoe_configs(aoes: dict, id_maps: CppIdMaps) -> list:
    """Convert Python AOEConfig dict to C++ AOEConfig list."""
    cpp_aoe_configs = []
    for aoe in aoes.values():
        cpp_aoe = CppAOEConfig()
        cpp_aoe.radius = aoe.radius
        cpp_aoe.is_static = aoe.is_static
        cpp_aoe.effect_self = aoe.effect_self

        _convert_filters(aoe.filters, cpp_aoe, id_maps, context="AOEConfig")
        convert_mutations(aoe.mutations, cpp_aoe, id_maps, context="AOEConfig")

        presence_deltas_list = []
        for resource_name, delta in aoe.presence_deltas.items():
            if resource_name not in id_maps.resource_name_to_id:
                raise ValueError(f"Unknown resource '{resource_name}' in AOEConfig presence_deltas")
            presence_deltas_list.append(CppResourceDelta(id_maps.resource_name_to_id[resource_name], delta))
        cpp_aoe.presence_deltas = presence_deltas_list

        cpp_aoe_configs.append(cpp_aoe)
    return cpp_aoe_configs


# ---------------------------------------------------------------------------
# Map rewriting
# ---------------------------------------------------------------------------


def rename_map_agents(map_grid: list[list[str]], rename_map: dict[str, list[str]]) -> list[list[str]]:
    """Rename collective agent cells to per-agent cell names."""
    counters: dict[str, int] = {name: 0 for name in rename_map}
    result = []
    for row in map_grid:
        new_row = []
        for cell in row:
            if cell in rename_map:
                idx = counters[cell]
                per_agent_names = rename_map[cell]
                if idx >= len(per_agent_names):
                    raise ValueError(
                        f"Map has more '{cell}' cells ({idx + 1}) than agents "
                        f"in the collective ({len(per_agent_names)})"
                    )
                new_row.append(per_agent_names[idx])
                counters[cell] = idx + 1
            else:
                new_row.append(cell)
        result.append(new_row)
    return result


# ---------------------------------------------------------------------------
# Top-level conversion
# ---------------------------------------------------------------------------


def convert_to_cpp_game_config(
    mettagrid_config: dict | GameConfig,
) -> tuple[CppGameConfig, dict[str, list[str]]]:
    """Convert a GameConfig to a CppGameConfig.

    Returns (cpp_game_config, agent_renames) where agent_renames maps
    collective cell names to per-agent cell names for map rewriting.
    """
    if isinstance(mettagrid_config, GameConfig):
        game_config = mettagrid_config
    else:
        config_dict = mettagrid_config.copy()
        if "obs" in config_dict and "features" in config_dict["obs"]:
            config_dict["obs"] = config_dict["obs"].copy()
            config_dict["obs"].pop("features", None)
        config_dict.pop("vibe_names", None)
        game_config = GameConfig(**config_dict)

    game_config.vibe_names = [vibe.name for vibe in game_config.actions.change_vibe.vibes]

    # Normalize to agents list
    has_agents_list = bool(game_config.agents)
    if not has_agents_list:
        game_config.agents = []
        for _ in range(game_config.num_agents):
            agent = game_config.agent.model_copy(update={"team_id": 0})
            game_config.agents.append(agent)

    # --- Build all name-to-id mappings once ---
    resource_names = list(game_config.resource_names)
    resource_name_to_id = {name: i for i, name in enumerate(resource_names)}

    type_names = set(game_config.objects.keys())
    for agent_config in game_config.agents:
        type_names.add(agent_config.name)
    type_names_sorted = sorted(type_names)
    type_id_by_type_name = {name: i for i, name in enumerate(type_names_sorted)}

    supported_vibes = game_config.actions.change_vibe.vibes
    vibe_name_to_id = {vibe.name: i for i, vibe in enumerate(supported_vibes)}

    collective_name_to_id = {name: idx for idx, name in enumerate(sorted(game_config.collectives.keys()))}

    first_agent_config_dict = game_config.agents[0].model_dump()
    default_resource_limit = first_agent_config_dict["inventory"]["default_limit"]

    limit_name_to_resource_ids: dict[str, list[int]] = {}
    for agent_config in game_config.agents:
        agent_inv_config = agent_config.model_dump().get("inventory", {})
        for limit_name, limit_config in agent_inv_config.get("limits", {}).items():
            if limit_name not in limit_name_to_resource_ids:
                limit_resource_names = limit_config.get("resources", [])
                limit_resource_ids = [
                    resource_name_to_id[name] for name in limit_resource_names if name in resource_name_to_id
                ]
                limit_name_to_resource_ids[limit_name] = limit_resource_ids

    all_tag_names: set[str] = {t.name for t in game_config.tags}
    for obj_name, obj_config in game_config.objects.items():
        all_tag_names.update(obj_config.tags)
        all_tag_names.add(typeTag(obj_name).name)
    for agent_config in game_config.agents:
        all_tag_names.update(agent_config.tags)
        all_tag_names.add(typeTag(agent_config.name).name)

    sorted_tag_names = sorted(all_tag_names)
    if len(sorted_tag_names) > 256:
        raise ValueError(
            f"Too many unique tags ({len(sorted_tag_names)}). Maximum supported is 256 due to uint8 limit."
        )
    tag_name_to_id: dict[str, int] = {name: i for i, name in enumerate(sorted_tag_names)}
    tag_id_to_name = {id: name for name, id in tag_name_to_id.items()}

    id_maps = CppIdMaps(
        resource_name_to_id=resource_name_to_id,
        tag_name_to_id=tag_name_to_id,
        vibe_name_to_id=vibe_name_to_id,
        collective_name_to_id=collective_name_to_id,
        limit_name_to_resource_ids=limit_name_to_resource_ids,
    )

    # --- Build agents ---

    objects_cpp_params = {}
    collective_groups: dict[str | int, list[tuple[int, Any]]] = {}
    for agent_idx, agent_config in enumerate(game_config.agents):
        group_key: str | int = agent_config.collective if agent_config.collective is not None else agent_config.team_id
        if group_key not in collective_groups:
            collective_groups[group_key] = []
        collective_groups[group_key].append((agent_idx, agent_config))

    def _build_one_agent_config(agent_cfg, group_id: int, group_name: str) -> CppAgentConfig:
        agent_props = agent_cfg.model_dump()

        reward_entries = []
        for reward_name, agent_reward in agent_cfg.rewards.items():
            entry = CppRewardEntry()
            if len(agent_reward.nums) != 1:
                raise ValueError(
                    f"Reward '{reward_name}' has {len(agent_reward.nums)} numerators, "
                    "but only a single numerator per reward is supported."
                )
            entry.numerator = resolve_game_value(agent_reward.nums[0], id_maps)
            entry.denominators = [resolve_game_value(d, id_maps) for d in agent_reward.denoms]
            entry.weight = agent_reward.weight
            if agent_reward.max is not None:
                entry.max_value = agent_reward.max
                entry.has_max = True
            reward_entries.append(entry)

        inv_config = agent_props.get("inventory", {})
        initial_inventory = {resource_name_to_id[k]: v for k, v in inv_config.get("initial", {}).items()}

        agent_tag_names = list(agent_cfg.tags) + [typeTag(agent_cfg.name).name]
        tag_ids = [tag_name_to_id[name] for name in agent_tag_names]

        limit_defs = []
        configured_resources = set()
        for resource_limit in inv_config.get("limits", {}).values():
            resource_ids = [resource_name_to_id[name] for name in resource_limit["resources"]]
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

        for resource_name in resource_names:
            if resource_name not in configured_resources:
                limit_defs.append(CppLimitDef([resource_name_to_id[resource_name]], default_resource_limit))

        inventory_config = CppInventoryConfig()
        inventory_config.limit_defs = limit_defs

        reward_config = CppRewardConfig()
        reward_config.entries = reward_entries

        cpp_agent_config = CppAgentConfig(
            type_id=type_id_by_type_name[agent_cfg.name],
            type_name=agent_cfg.name,
            group_id=group_id,
            group_name=group_name,
            freeze_duration=agent_props["freeze_duration"],
            initial_vibe=agent_props["vibe"],
            inventory_config=inventory_config,
            reward_config=reward_config,
            initial_inventory=initial_inventory,
        )
        cpp_agent_config.tag_ids = tag_ids

        if agent_cfg.collective and agent_cfg.collective in collective_name_to_id:
            cpp_agent_config.collective_id = collective_name_to_id[agent_cfg.collective]

        if agent_cfg.aoes:
            cpp_agent_config.aoe_configs = _convert_aoe_configs(agent_cfg.aoes, id_maps)

        if agent_cfg.on_tick:
            cpp_agent_config.on_tick = _convert_handlers(agent_cfg.on_tick, id_maps)

        if agent_cfg.log_sum_stats:
            cpp_log_sum_stats = []
            for ls_cfg in agent_cfg.log_sum_stats:
                cpp_ls = CppLogSumStatConfig()
                cpp_ls.stat_name = ls_cfg.stat_name
                cpp_ls.stat_suffix = ls_cfg.stat_suffix
                cpp_ls.items = [resource_name_to_id[r] for r in ls_cfg.resources]
                cpp_log_sum_stats.append(cpp_ls)
            cpp_agent_config.log_sum_stats = cpp_log_sum_stats

        return cpp_agent_config

    agent_renames: dict[str, list[str]] = {}
    collective_to_id = {name: idx for idx, name in enumerate(collective_groups.keys())}
    for collective, collective_agents in collective_groups.items():
        _, first_agent = collective_agents[0]

        first_agent_tags = set(first_agent.tags)
        for agent_idx, agent_config in collective_agents[1:]:
            if set(agent_config.tags) != first_agent_tags:
                raise ValueError(
                    f"All agents in collective {collective} must have identical tags. "
                    f"Agent 0 has tags {sorted(first_agent_tags)}, "
                    f"but agent {agent_idx} has tags {sorted(agent_config.tags)}. "
                    f"Tags are currently applied per-collective, not per-agent."
                )

        group_id = collective_to_id[collective]
        team_names = {0: "red", 1: "blue", 2: "green", 3: "yellow", 4: "purple", 5: "orange"}
        if isinstance(collective, str):
            group_name = collective
        elif isinstance(collective, int) and collective in team_names:
            group_name = team_names[collective]
        else:
            group_name = f"group_{group_id}"

        canonical_cell = "agent." + group_name

        per_agent_cells: list[str] = []
        for idx, (_, agent_cfg) in enumerate(collective_agents):
            cell_name = f"agent.{group_name}.{idx}"
            per_agent_cells.append(cell_name)
            objects_cpp_params[cell_name] = _build_one_agent_config(agent_cfg, group_id, group_name)
        objects_cpp_params[canonical_cell] = objects_cpp_params[per_agent_cells[0]]
        if len(collective_agents) > 1:
            agent_renames[canonical_cell] = per_agent_cells

        alias_cells = [f"agent.team_{group_id}"]
        if isinstance(collective, int) and collective != group_id:
            alias_cells.append(f"agent.team_{collective}")
        team_names = {0: "red", 1: "blue", 2: "green", 3: "yellow", 4: "purple", 5: "orange"}
        if group_id in team_names:
            alias_cells.append(f"agent.{team_names[group_id]}")
        if isinstance(collective, int) and collective in team_names and collective != group_id:
            alias_cells.append(f"agent.{team_names[collective]}")
        if group_id == 0:
            alias_cells.extend(["agent.default", "agent.agent"])
        for alias in alias_cells:
            objects_cpp_params[alias] = objects_cpp_params[canonical_cell]
            if canonical_cell in agent_renames:
                agent_renames[alias] = agent_renames[canonical_cell]

    # --- Build objects ---

    for object_type, object_config in game_config.objects.items():
        cpp_config = None

        type_id = type_id_by_type_name[object_type]
        object_tag_names = list(object_config.tags) + [typeTag(object_type).name]
        tag_ids = [tag_name_to_id[name] for name in object_tag_names]

        if isinstance(object_config, WallConfig):
            cpp_config = CppWallConfig(type_id=type_id, type_name=object_type, initial_vibe=object_config.vibe)
        elif isinstance(object_config, GridObjectConfig):
            cpp_config = CppGridObjectConfig(type_id=type_id, type_name=object_type, initial_vibe=object_config.vibe)

            if object_config.inventory and object_config.inventory.initial:
                initial_inventory_cpp = {}
                for resource, amount in object_config.inventory.initial.items():
                    if resource in resource_name_to_id:
                        initial_inventory_cpp[resource_name_to_id[resource]] = amount
                cpp_config.initial_inventory = initial_inventory_cpp

                limit_defs = []
                for resource_limit in object_config.inventory.limits.values():
                    resource_list = resource_limit.resources
                    resource_ids = [resource_name_to_id[name] for name in resource_list if name in resource_name_to_id]
                    if resource_ids:
                        modifier_ids = {
                            resource_name_to_id[name]: bonus
                            for name, bonus in resource_limit.modifiers.items()
                            if name in resource_name_to_id
                        }
                        limit_defs.append(
                            CppLimitDef(resource_ids, resource_limit.min, resource_limit.max, modifier_ids)
                        )
                inventory_config = CppInventoryConfig()
                inventory_config.limit_defs = limit_defs
                cpp_config.inventory_config = inventory_config
        else:
            raise ValueError(f"Unknown object type: {object_type}")

        if cpp_config is not None:
            cpp_config.tag_ids = tag_ids

            if object_config.collective and object_config.collective in collective_name_to_id:
                cpp_config.collective_id = collective_name_to_id[object_config.collective]

            if object_config.on_use_handlers:
                cpp_config.on_use_handler = _create_on_use_handler(object_config.on_use_handlers, id_maps)
            if object_config.aoes:
                cpp_config.aoe_configs = _convert_aoe_configs(object_config.aoes, id_maps)

            objects_cpp_params[object_config.map_name or object_type] = cpp_config

    # --- Build top-level game params ---

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

    if "obs" in game_cpp_params:
        obs_config = game_cpp_params.pop("obs")
        game_cpp_params["obs_width"] = obs_config["width"]
        game_cpp_params["obs_height"] = obs_config["height"]
        game_cpp_params["num_observation_tokens"] = obs_config["num_tokens"]
        game_cpp_params["token_value_base"] = obs_config.get("token_value_base", 256)

    id_map = game_config.id_map()
    game_cpp_params["feature_ids"] = {feature.name: feature.id for feature in id_map.features()}

    global_obs_config = game_config.obs.global_obs

    from mettagrid.config.game_value import InventoryValue, StatValue  # noqa: PLC0415

    obs_cpp = []
    for game_value in global_obs_config.obs:
        cpp_obs = CppObsValueConfig()
        cpp_obs.value = resolve_game_value(game_value, id_maps)
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
        goal_obs=global_obs_config.goal_obs,
        local_position=global_obs_config.local_position,
        obs=obs_cpp,
    )
    game_cpp_params["global_obs"] = global_obs_cpp

    # --- Actions ---

    actions_config = game_config.actions
    actions_cpp_params = {}

    def process_action_config(action_name: str, action_config) -> dict[str, Any]:
        if not action_config.enabled:
            return {"consumed_resources": {}, "required_resources": {}}

        missing_consumed = [r for r in action_config.consumed_resources if r not in resource_name_to_id]
        if missing_consumed:
            raise ValueError(
                f"Action '{action_name}' has consumed_resources {missing_consumed} that are not in "
                f"resource_names. These resources will be ignored, making the action free! "
                f"Either add these resources to resource_names or disable the action."
            )

        consumed_resources = {resource_name_to_id[k]: int(v) for k, v in action_config.consumed_resources.items()}
        required_source = action_config.required_resources or action_config.consumed_resources
        required_resources = {resource_name_to_id[k]: int(v) for k, v in required_source.items()}

        return {"consumed_resources": consumed_resources, "required_resources": required_resources}

    action_params = process_action_config("noop", actions_config.noop)
    actions_cpp_params["noop"] = CppActionConfig(**action_params)

    action_params = process_action_config("move", actions_config.move)
    action_params["allowed_directions"] = actions_config.move.allowed_directions
    actions_cpp_params["move"] = CppMoveActionConfig(**action_params)

    action_params = process_action_config("attack", actions_config.attack)
    attack_cfg = actions_config.attack
    action_params["defense_resources"] = {resource_name_to_id[k]: v for k, v in attack_cfg.defense_resources.items()}
    action_params["armor_resources"] = {resource_name_to_id[k]: v for k, v in attack_cfg.armor_resources.items()}
    action_params["weapon_resources"] = {resource_name_to_id[k]: v for k, v in attack_cfg.weapon_resources.items()}
    success_actor = {resource_name_to_id[k]: v for k, v in attack_cfg.success.actor_inv_delta.items()}
    success_target = {resource_name_to_id[k]: v for k, v in attack_cfg.success.target_inv_delta.items()}
    success_loot = [resource_name_to_id[name] for name in attack_cfg.success.loot]
    action_params["success"] = CppAttackOutcome(success_actor, success_target, success_loot, attack_cfg.success.freeze)
    action_params["enabled"] = attack_cfg.enabled
    for vibe in attack_cfg.vibes:
        if vibe not in vibe_name_to_id:
            raise ValueError(f"Unknown vibe name '{vibe}' in attack.vibes")
    action_params["vibes"] = [vibe_name_to_id[vibe] for vibe in attack_cfg.vibes]
    for vibe in attack_cfg.vibe_bonus:
        if vibe not in vibe_name_to_id:
            raise ValueError(f"Unknown vibe name '{vibe}' in attack.vibe_bonus")
    action_params["vibe_bonus"] = {vibe_name_to_id[vibe]: bonus for vibe, bonus in attack_cfg.vibe_bonus.items()}
    actions_cpp_params["attack"] = CppAttackActionConfig(**action_params)

    action_params = process_action_config("change_vibe", actions_config.change_vibe)
    num_vibes = len(actions_config.change_vibe.vibes) if actions_config.change_vibe.enabled else 0
    action_params["number_of_vibes"] = num_vibes
    actions_cpp_params["change_vibe"] = CppChangeVibeActionConfig(**action_params)

    game_cpp_params["actions"] = actions_cpp_params
    game_cpp_params["objects"] = objects_cpp_params
    game_cpp_params["tag_id_map"] = tag_id_to_name

    # --- Collectives ---

    collectives_cpp = {}
    for collective_name, collective_cfg in game_config.collectives.items():
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

        initial_inventory_cpp = {}
        for resource, amount in collective_cfg.inventory.initial.items():
            if resource in resource_name_to_id:
                initial_inventory_cpp[resource_name_to_id[resource]] = amount

        cpp_collective_config = CppCollectiveConfig(collective_name)
        cpp_collective_config.inventory_config = inventory_config
        cpp_collective_config.initial_inventory = initial_inventory_cpp
        collectives_cpp[collective_name] = cpp_collective_config

    game_cpp_params["collectives"] = collectives_cpp

    # --- Events ---

    if game_config.events:
        game_cpp_params["events"] = _convert_event_configs(game_config.events, id_maps)

    return CppGameConfig(**game_cpp_params), agent_renames
