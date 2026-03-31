from typing import Any

from mettagrid.config.cpp_id_maps import CppIdMaps
from mettagrid.config.mettagrid_c_mutations import convert_entity_ref, convert_mutations
from mettagrid.config.mettagrid_c_value_config import resolve_game_value
from mettagrid.config.mettagrid_config import (
    GameConfig,
    GridObjectConfig,
    WallConfig,
)
from mettagrid.config.query import Query
from mettagrid.config.tag import typeTag
from mettagrid.mettagrid_c import ActionConfig as CppActionConfig
from mettagrid.mettagrid_c import AgentConfig as CppAgentConfig
from mettagrid.mettagrid_c import AOEConfig as CppAOEConfig
from mettagrid.mettagrid_c import AttackActionConfig as CppAttackActionConfig
from mettagrid.mettagrid_c import AttackOutcome as CppAttackOutcome
from mettagrid.mettagrid_c import ChangeVibeActionConfig as CppChangeVibeActionConfig
from mettagrid.mettagrid_c import ClosureQueryConfig as CppClosureQueryConfig
from mettagrid.mettagrid_c import EventConfig as CppEventConfig
from mettagrid.mettagrid_c import FilteredQueryConfig as CppFilteredQueryConfig
from mettagrid.mettagrid_c import GameConfig as CppGameConfig
from mettagrid.mettagrid_c import GameValueFilterConfig as CppGameValueFilterConfig
from mettagrid.mettagrid_c import GlobalObsConfig as CppGlobalObsConfig
from mettagrid.mettagrid_c import GridObjectConfig as CppGridObjectConfig
from mettagrid.mettagrid_c import Handler as CppHandler
from mettagrid.mettagrid_c import HandlerConfig as CppHandlerConfig
from mettagrid.mettagrid_c import HandlerMode as CppHandlerMode
from mettagrid.mettagrid_c import InventoryConfig as CppInventoryConfig
from mettagrid.mettagrid_c import LimitDef as CppLimitDef
from mettagrid.mettagrid_c import (
    MaterializedQueryTag as CppMaterializedQueryTag,  # pyright: ignore[reportAttributeAccessIssue]
)
from mettagrid.mettagrid_c import MaxDistanceFilterConfig as CppMaxDistanceFilterConfig
from mettagrid.mettagrid_c import MoveActionConfig as CppMoveActionConfig
from mettagrid.mettagrid_c import MultiHandler as CppMultiHandler
from mettagrid.mettagrid_c import NegFilterConfig as CppNegFilterConfig
from mettagrid.mettagrid_c import ObsValueConfig as CppObsValueConfig
from mettagrid.mettagrid_c import OrFilterConfig as CppOrFilterConfig  # pyright: ignore[reportAttributeAccessIssue]
from mettagrid.mettagrid_c import QueryOrderBy as CppQueryOrderBy
from mettagrid.mettagrid_c import ResourceDelta as CppResourceDelta
from mettagrid.mettagrid_c import ResourceFilterConfig as CppResourceFilterConfig
from mettagrid.mettagrid_c import RewardConfig as CppRewardConfig
from mettagrid.mettagrid_c import RewardEntry as CppRewardEntry
from mettagrid.mettagrid_c import (
    SharedTagPrefixFilterConfig as CppSharedTagPrefixFilterConfig,  # pyright: ignore[reportAttributeAccessIssue]
)
from mettagrid.mettagrid_c import TagPrefixFilterConfig as CppTagPrefixFilterConfig
from mettagrid.mettagrid_c import TagQueryConfig as CppTagQueryConfig
from mettagrid.mettagrid_c import TargetIsUsableFilterConfig as CppTargetIsUsableFilterConfig
from mettagrid.mettagrid_c import TargetLocEmptyFilterConfig as CppTargetLocEmptyFilterConfig
from mettagrid.mettagrid_c import TerritoryConfig as CppTerritoryConfig  # pyright: ignore[reportAttributeAccessIssue]
from mettagrid.mettagrid_c import (
    TerritoryControlConfig as CppTerritoryControlConfig,  # pyright: ignore[reportAttributeAccessIssue]
)
from mettagrid.mettagrid_c import VibeFilterConfig as CppVibeFilterConfig
from mettagrid.mettagrid_c import WallConfig as CppWallConfig
from mettagrid.mettagrid_c import make_query_config


def _resolve_tag_prefix(prefix: str, tag_name_to_id: dict) -> list[int]:
    return [tag_id for tag_name, tag_id in tag_name_to_id.items() if tag_name.startswith(prefix)]


# ---------------------------------------------------------------------------
# Tag query conversion (shared by proximity filters and mutation queries)
# ---------------------------------------------------------------------------


def _convert_tag_query(query, id_maps: CppIdMaps, context: str = ""):
    """Convert a Python Query or ClosureQuery to a C++ QueryConfig (wrapped in shared_ptr).

    Used by MaxDistanceFilter (proximity), QueryInventoryMutation, and QueryTags.
    """
    if isinstance(query, str):
        return _convert_tag_query(Query(source=query), id_maps, context)

    query_type = getattr(query, "query_type", "query")

    if query_type == "materialized":
        return _convert_tag_query(Query(source=query.tag), id_maps, context)

    if query_type == "closure":
        return _convert_closure_query(query, id_maps, context)

    source = query.source
    if not isinstance(source, str):
        inner_cpp = _convert_tag_query(source, id_maps, f"{context} inner")
        cpp_q = CppFilteredQueryConfig()
        cpp_q.set_source(inner_cpp)
        if query.max_items is not None:
            cpp_q.max_items = query.max_items
        if query.order_by == "random":
            cpp_q.order_by = CppQueryOrderBy.random
        _convert_filters(query.filters, cpp_q, id_maps, context=context)
        return make_query_config(cpp_q)

    query_tag = source
    if query_tag not in id_maps.tag_name_to_id:
        raise ValueError(
            f"Tag query in {context} references unknown tag '{query_tag}'. Add it to GameConfig.tags or object tags."
        )

    tag_query = CppTagQueryConfig()
    tag_query.tag_id = id_maps.tag_name_to_id[query_tag]
    if query.max_items is not None:
        tag_query.max_items = query.max_items
    if query.order_by == "random":
        tag_query.order_by = CppQueryOrderBy.random

    _convert_filters(query.filters, tag_query, id_maps, context=context)

    return make_query_config(tag_query)


def _convert_closure_query(query, id_maps: CppIdMaps, context: str = ""):
    """Convert a ClosureQuery to a C++ ClosureQueryConfig."""
    cpp_source = _convert_tag_query(query.source, id_maps, context=f"{context} closure.source")
    cpp_candidates = _convert_tag_query(query.candidates, id_maps, context=f"{context} closure.candidates")

    cpp_q = CppClosureQueryConfig()
    cpp_q.set_source(cpp_source)
    cpp_q.set_candidates(cpp_candidates)
    if query.max_items is not None:
        cpp_q.max_items = query.max_items
    if query.order_by == "random":
        cpp_q.order_by = CppQueryOrderBy.random

    if query.edge_filters:
        _convert_filters(
            query.edge_filters,
            cpp_q,
            id_maps,
            context=f"{context} closure.edge_filters",
            method_prefix="edge_",
        )

    if query.filters:
        _convert_filters(query.filters, cpp_q, id_maps, context=f"{context} closure.filters", method_prefix="result_")

    return make_query_config(cpp_q)


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
        if filter_config.tag not in id_maps.tag_name_to_id:
            return None
        return (
            "tag_prefix",
            CppTagPrefixFilterConfig(
                entity=convert_entity_ref(filter_config.target),
                tag_ids=[id_maps.tag_name_to_id[filter_config.tag]],
            ),
        )

    if ft == "tag_prefix":
        tag_ids = _resolve_tag_prefix(filter_config.tag_prefix, id_maps.tag_name_to_id)
        if not tag_ids:
            raise ValueError(
                f"TagPrefixFilter prefix '{filter_config.tag_prefix}' matched no tags. "
                f"Available tags: {sorted(id_maps.tag_name_to_id.keys())}"
            )
        return (
            "tag_prefix",
            CppTagPrefixFilterConfig(
                entity=convert_entity_ref(filter_config.target),
                tag_ids=tag_ids,
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
        cpp_filter = CppMaxDistanceFilterConfig()
        cpp_filter.entity = convert_entity_ref(filter_config.target)
        cpp_filter.radius = filter_config.radius
        if filter_config.query is not None:
            source = _convert_tag_query(
                filter_config.query,
                id_maps,
                context=f"{context} max_distance source" if context else "max_distance source",
            )
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

    if ft == "target_loc_empty":
        return ("target_loc_empty", CppTargetLocEmptyFilterConfig())

    if ft == "target_is_usable":
        return ("target_is_usable", CppTargetIsUsableFilterConfig())

    return None


# ---------------------------------------------------------------------------
# Filter attachment: all C++ targets use add_<type>_filter
# ---------------------------------------------------------------------------

_FILTER_TYPE_TO_METHOD = {
    "resource": "add_resource_filter",
    "vibe": "add_vibe_filter",
    "tag_prefix": "add_tag_prefix_filter",
    "shared_tag_prefix": "add_shared_tag_prefix_filter",
    "max_distance": "add_max_distance_filter",
    "game_value": "add_game_value_filter",
    "neg": "add_neg_filter",
    "or": "add_or_filter",
    "target_loc_empty": "add_target_loc_empty_filter",
    "target_is_usable": "add_target_is_usable_filter",
}


def _attach(target, type_key: str, result, *, method_prefix: str = ""):
    """Attach converted filter(s) to a C++ target."""
    base = _FILTER_TYPE_TO_METHOD[type_key]
    method_name = f"add_{method_prefix}{base[len('add_') :]}" if method_prefix else base
    method = getattr(target, method_name)
    if isinstance(result, list):
        for item in result:
            method(item)
    else:
        method(result)


# ---------------------------------------------------------------------------
# Filter conversion: the three public entry points
# ---------------------------------------------------------------------------


def _convert_filters(filters, cpp_target, id_maps: CppIdMaps, context: str = "", *, method_prefix: str = ""):
    """Convert Python filters to C++ and add them to the target config."""
    for f in filters:
        converted = _convert_one_filter(f, id_maps, context)
        if converted is not None:
            _attach(cpp_target, *converted, method_prefix=method_prefix)


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

        cpp_event.set_target_query(
            _convert_tag_query(event.target_query, id_maps, context=f"event '{event_name}' target_query")
        )

        _convert_filters(event.filters, cpp_event, id_maps, context=f"event '{event_name}'")
        _convert_event_mutations(event.mutations, cpp_event, id_maps, context=f"event '{event_name}'")

        cpp_events[event_name] = cpp_event
    return cpp_events


def _convert_event_mutations(mutations, cpp_target, id_maps: CppIdMaps, context: str):
    """Convert Python mutations for events."""
    convert_mutations(mutations, cpp_target, id_maps, context)


def _convert_on_tag_lifecycle_handlers(
    handlers_dict: dict, cpp_config: object, id_maps: CppIdMaps, *, add_method: str, label: str
):
    """Convert on_tag_add/on_tag_remove handler dicts to C++ and attach them."""
    adder = getattr(cpp_config, add_method)
    for tag_prefix, handler in handlers_dict.items():
        tag_ids = _resolve_tag_prefix(tag_prefix, id_maps.tag_name_to_id)
        if not tag_ids:
            raise ValueError(
                f"{label} prefix '{tag_prefix}' matched no tags. "
                f"Available tags: {sorted(id_maps.tag_name_to_id.keys())}"
            )
        cpp_handler = CppHandlerConfig(tag_prefix)
        _convert_filters(handler.filters, cpp_handler, id_maps, context=f"{label} '{tag_prefix}'")
        convert_mutations(handler.mutations, cpp_handler, id_maps, context=f"{label} '{tag_prefix}'")
        for tag_id in tag_ids:
            adder(tag_id, cpp_handler)


def _convert_aoe_configs(aoes: dict, id_maps: CppIdMaps) -> list:
    """Convert Python AOEConfig dict to C++ AOEConfig list."""
    cpp_aoe_configs = []
    for aoe_config in aoes.values():
        cpp_aoe_config = CppAOEConfig()
        cpp_aoe_config.radius = aoe_config.radius
        cpp_aoe_config.is_static = aoe_config.is_static
        cpp_aoe_config.effect_self = aoe_config.effect_self

        _convert_filters(aoe_config.filters, cpp_aoe_config, id_maps, context="AOEConfig")
        convert_mutations(aoe_config.mutations, cpp_aoe_config, id_maps, context="AOEConfig")

        presence_deltas_list = []
        for resource_name, delta in aoe_config.presence_deltas.items():
            if resource_name not in id_maps.resource_name_to_id:
                raise ValueError(f"Unknown resource '{resource_name}' in AOEConfig presence_deltas")
            presence_deltas_list.append(CppResourceDelta(id_maps.resource_name_to_id[resource_name], delta))
        cpp_aoe_config.presence_deltas = presence_deltas_list

        cpp_aoe_configs.append(cpp_aoe_config)
    return cpp_aoe_configs


def _convert_handler_to_cpp(handler, id_maps: CppIdMaps, context: str) -> CppHandlerConfig:
    """Convert a Python Handler to a C++ HandlerConfig."""
    cpp_handler = CppHandlerConfig(context)
    _convert_filters(handler.filters, cpp_handler, id_maps, context=context)
    convert_mutations(handler.mutations, cpp_handler, id_maps, context=context)
    return cpp_handler


def _convert_game_territory_configs(
    territories: dict, id_maps: CppIdMaps, territory_name_to_index: dict[str, int]
) -> list:
    """Convert game-level Python TerritoryConfig dict to C++ TerritoryConfig list (ordered by index)."""
    cpp_configs = [CppTerritoryConfig() for _ in range(len(territories))]
    for name, territory_config in territories.items():
        idx = territory_name_to_index[name]
        cpp_tc = cpp_configs[idx]

        cpp_tc.tag_prefix_ids = _resolve_tag_prefix(territory_config.tag_prefix, id_maps.tag_name_to_id)

        ctx = f"territory '{name}'"
        cpp_tc.on_enter = [
            _convert_handler_to_cpp(h, id_maps, f"{ctx}.on_enter.{k}") for k, h in territory_config.on_enter.items()
        ]
        cpp_tc.on_exit = [
            _convert_handler_to_cpp(h, id_maps, f"{ctx}.on_exit.{k}") for k, h in territory_config.on_exit.items()
        ]
        cpp_tc.presence = [
            _convert_handler_to_cpp(h, id_maps, f"{ctx}.presence.{k}") for k, h in territory_config.presence.items()
        ]
    return cpp_configs


def _convert_territory_controls(controls: list, id_maps: CppIdMaps, territory_name_to_index: dict[str, int]) -> list:
    """Convert per-object Python TerritoryControlConfig list to C++ TerritoryControlConfig list."""
    cpp_controls = []
    for tc in controls:
        if tc.territory not in territory_name_to_index:
            raise ValueError(
                f"TerritoryControlConfig references unknown territory '{tc.territory}'. "
                f"Available: {sorted(territory_name_to_index.keys())}"
            )
        cpp_tc = CppTerritoryControlConfig()
        cpp_tc.strength = tc.strength
        cpp_tc.decay = tc.decay
        cpp_tc.territory_index = territory_name_to_index[tc.territory]
        cpp_controls.append(cpp_tc)
    return cpp_controls


# ---------------------------------------------------------------------------
# Map rewriting
# ---------------------------------------------------------------------------


def rename_map_agents(map_grid: list[list[str]], rename_map: dict[str, list[str]]) -> list[list[str]]:
    """Rename agent group cells to per-agent cell names."""
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
                        f"Map has more '{cell}' cells ({idx + 1}) than agents in the group ({len(per_agent_names)})"
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
    group cell names to per-agent cell names for map rewriting.
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

    type_names = {cfg.name for cfg in game_config.objects.values()}
    for agent_config in game_config.agents:
        type_names.add(agent_config.name)
    type_names_sorted = sorted(type_names)
    type_id_by_type_name = {name: i for i, name in enumerate(type_names_sorted)}

    supported_vibes = game_config.actions.change_vibe.vibes
    vibe_name_to_id = {vibe.name: i for i, vibe in enumerate(supported_vibes)}

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

    materialized_tag_names: set[str] = {mq.tag for mq in game_config.materialize_queries}
    static_tag_names: set[str] = set(game_config.tags)
    for obj_config in game_config.objects.values():
        static_tag_names.update(obj_config.tags)
        static_tag_names.add(typeTag(obj_config.name))
    for agent_config in game_config.agents:
        static_tag_names.update(agent_config.tags)
        static_tag_names.add(typeTag(agent_config.name))

    all_tag_names = materialized_tag_names | static_tag_names
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
        limit_name_to_resource_ids=limit_name_to_resource_ids,
    )

    territory_name_to_index: dict[str, int] = {name: i for i, name in enumerate(game_config.territories.keys())}

    # --- Build agents ---

    objects_cpp_params = {}
    team_groups: dict[int, list[tuple[int, Any]]] = {}
    for agent_idx, agent_config in enumerate(game_config.agents):
        group_key = agent_config.team_id
        if group_key not in team_groups:
            team_groups[group_key] = []
        team_groups[group_key].append((agent_idx, agent_config))

    def _build_one_agent_config(agent_cfg, group_id: int, group_name: str) -> CppAgentConfig:
        agent_props = agent_cfg.model_dump()

        reward_entries = []
        for _, agent_reward in agent_cfg.rewards.items():
            entry = CppRewardEntry()
            entry.reward = resolve_game_value(agent_reward.reward, id_maps)
            entry.accumulate = agent_reward.per_tick
            reward_entries.append(entry)

        inv_config = agent_props.get("inventory", {})
        initial_inventory = {resource_name_to_id[k]: v for k, v in inv_config.get("initial", {}).items()}

        agent_tag_names = list(agent_cfg.tags) + [typeTag(agent_cfg.name)]
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
            min_val = resource_limit.get("base", resource_limit.get("limit", 0))
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
            initial_vibe=agent_props["vibe"],
            inventory_config=inventory_config,
            reward_config=reward_config,
            initial_inventory=initial_inventory,
        )
        cpp_agent_config.tag_ids = tag_ids

        if agent_cfg.aoes:
            cpp_agent_config.aoe_configs = _convert_aoe_configs(agent_cfg.aoes, id_maps)

        if agent_cfg.territory_controls:
            cpp_agent_config.territory_controls = _convert_territory_controls(  # pyright: ignore[reportAttributeAccessIssue]
                agent_cfg.territory_controls, id_maps, territory_name_to_index
            )

        if agent_cfg.on_tag_remove:
            _convert_on_tag_lifecycle_handlers(
                agent_cfg.on_tag_remove,
                cpp_agent_config,
                id_maps,
                add_method="add_on_tag_remove_handler",
                label="on_tag_remove",
            )

        if agent_cfg.on_tick:
            cpp_agent_config.on_tick = _convert_handlers(agent_cfg.on_tick, id_maps)

        if agent_cfg.on_use_handlers:
            cpp_agent_config.on_use_handler = _create_on_use_handler(agent_cfg.on_use_handlers, id_maps)

        return cpp_agent_config

    agent_renames: dict[str, list[str]] = {}
    group_id_map = {team_id: idx for idx, team_id in enumerate(team_groups.keys())}
    for team_id, team_agents in team_groups.items():
        _, first_agent = team_agents[0]

        first_agent_tags = set(first_agent.tags)
        for agent_idx, agent_config in team_agents[1:]:
            if set(agent_config.tags) != first_agent_tags:
                raise ValueError(
                    f"All agents in team {team_id} must have identical tags. "
                    f"Agent 0 has tags {sorted(first_agent_tags)}, "
                    f"but agent {agent_idx} has tags {sorted(agent_config.tags)}. "
                    f"Tags are currently applied per-team, not per-agent."
                )

        group_id = group_id_map[team_id]
        team_names = {0: "red", 1: "blue", 2: "green", 3: "yellow", 4: "purple", 5: "orange"}
        if team_id in team_names:
            group_name = team_names[team_id]
        else:
            group_name = f"group_{group_id}"

        canonical_cell = "agent." + group_name

        per_agent_cells: list[str] = []
        for idx, (_, agent_cfg) in enumerate(team_agents):
            cell_name = f"agent.{group_name}.{idx}"
            per_agent_cells.append(cell_name)
            objects_cpp_params[cell_name] = _build_one_agent_config(agent_cfg, group_id, group_name)
        objects_cpp_params[canonical_cell] = objects_cpp_params[per_agent_cells[0]]
        if len(team_agents) > 1:
            agent_renames[canonical_cell] = per_agent_cells

        alias_cells = [f"agent.team_{group_id}"]
        if team_id != group_id:
            alias_cells.append(f"agent.team_{team_id}")
        if group_id in team_names:
            alias_cells.append(f"agent.{team_names[group_id]}")
        if team_id in team_names and team_id != group_id:
            alias_cells.append(f"agent.{team_names[team_id]}")
        if group_id == 0:
            alias_cells.extend(["agent.default", "agent.agent"])
        for alias in alias_cells:
            objects_cpp_params[alias] = objects_cpp_params[canonical_cell]
            if canonical_cell in agent_renames:
                agent_renames[alias] = agent_renames[canonical_cell]

    # --- Build objects ---

    for object_key, object_config in game_config.objects.items():
        cpp_config = None

        type_id = type_id_by_type_name[object_config.name]
        object_tag_names = list(object_config.tags) + [typeTag(object_config.name)]
        tag_ids = [tag_name_to_id[name] for name in object_tag_names]

        if isinstance(object_config, WallConfig):
            cpp_config = CppWallConfig(type_id=type_id, type_name=object_config.name, initial_vibe=object_config.vibe)
        elif isinstance(object_config, GridObjectConfig):
            cpp_config = CppGridObjectConfig(
                type_id=type_id, type_name=object_config.name, initial_vibe=object_config.vibe
            )

            if object_config.inventory:
                if object_config.inventory.initial:
                    initial_inventory_cpp = {}
                    for resource, amount in object_config.inventory.initial.items():
                        if resource in resource_name_to_id:
                            initial_inventory_cpp[resource_name_to_id[resource]] = amount
                    cpp_config.initial_inventory = initial_inventory_cpp

                obj_default_limit = object_config.inventory.default_limit
                limit_defs = []
                configured_resources: set[str] = set()
                for resource_limit in object_config.inventory.limits.values():
                    resource_list = resource_limit.resources
                    resource_ids = [resource_name_to_id[name] for name in resource_list if name in resource_name_to_id]
                    configured_resources.update(resource_list)
                    if resource_ids:
                        modifier_ids = {
                            resource_name_to_id[name]: bonus
                            for name, bonus in resource_limit.modifiers.items()
                            if name in resource_name_to_id
                        }
                        limit_defs.append(
                            CppLimitDef(resource_ids, resource_limit.base, resource_limit.max, modifier_ids)
                        )
                # Apply default_limit to resources with initial values but no explicit limit.
                for resource_name in object_config.inventory.initial:
                    if resource_name not in configured_resources and resource_name in resource_name_to_id:
                        limit_defs.append(CppLimitDef([resource_name_to_id[resource_name]], obj_default_limit))
                if limit_defs:
                    inventory_config = CppInventoryConfig()
                    inventory_config.limit_defs = limit_defs
                    cpp_config.inventory_config = inventory_config
        else:
            raise ValueError(f"Unknown object type: {object_config.name} (key={object_key})")

        if cpp_config is not None:
            cpp_config.tag_ids = tag_ids

            if object_config.on_use_handlers:
                cpp_config.on_use_handler = _create_on_use_handler(object_config.on_use_handlers, id_maps)
            if object_config.aoes:
                cpp_config.aoe_configs = _convert_aoe_configs(object_config.aoes, id_maps)
            if object_config.territory_controls:
                cpp_config.territory_controls = _convert_territory_controls(  # pyright: ignore[reportAttributeAccessIssue]
                    object_config.territory_controls, id_maps, territory_name_to_index
                )
            if object_config.on_tag_remove:
                _convert_on_tag_lifecycle_handlers(
                    object_config.on_tag_remove,
                    cpp_config,
                    id_maps,
                    add_method="add_on_tag_remove_handler",
                    label="on_tag_remove",
                )

            objects_cpp_params[object_config.map_name] = cpp_config

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
    if "materialize_queries" in game_cpp_params:
        del game_cpp_params["materialize_queries"]
    if "territories" in game_cpp_params:
        del game_cpp_params["territories"]
    if "render" in game_cpp_params:
        del game_cpp_params["render"]
    if "talk" in game_cpp_params:
        del game_cpp_params["talk"]
    if "on_tick" in game_cpp_params:
        del game_cpp_params["on_tick"]

    if "obs" in game_cpp_params:
        obs_config = game_cpp_params.pop("obs")
        game_cpp_params["obs_width"] = obs_config["width"]
        game_cpp_params["obs_height"] = obs_config["height"]
        game_cpp_params["num_observation_tokens"] = obs_config["num_tokens"]
        game_cpp_params["token_value_base"] = obs_config.get("token_value_base", 256)

    id_map = game_config.id_map()
    game_cpp_params["feature_ids"] = {feature.name: feature.id for feature in id_map.features()}

    global_obs_config = game_config.obs.global_obs

    obs_cpp = []
    for feature_name, game_value in global_obs_config.obs.items():
        cpp_obs = CppObsValueConfig()
        cpp_obs.value = resolve_game_value(game_value, id_maps)
        cpp_obs.feature_id = game_cpp_params["feature_ids"][feature_name]
        obs_cpp.append(cpp_obs)

    global_obs_cpp = CppGlobalObsConfig(
        episode_completion_pct=global_obs_config.episode_completion_pct,
        last_action=global_obs_config.last_action,
        last_action_move=global_obs_config.last_action_move,
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
    if actions_config.move.handlers:
        action_params["handlers"] = _convert_handlers(
            {h.name or f"move_handler_{i}": h for i, h in enumerate(actions_config.move.handlers)},
            id_maps,
        )
    actions_cpp_params["move"] = CppMoveActionConfig(**action_params)

    action_params = process_action_config("attack", actions_config.attack)
    attack_cfg = actions_config.attack
    action_params["defense_resources"] = {resource_name_to_id[k]: v for k, v in attack_cfg.defense_resources.items()}
    action_params["armor_resources"] = {resource_name_to_id[k]: v for k, v in attack_cfg.armor_resources.items()}
    action_params["weapon_resources"] = {resource_name_to_id[k]: v for k, v in attack_cfg.weapon_resources.items()}
    success_actor = {resource_name_to_id[k]: v for k, v in attack_cfg.success.actor_inv_delta.items()}
    success_target = {resource_name_to_id[k]: v for k, v in attack_cfg.success.target_inv_delta.items()}
    success_loot = [resource_name_to_id[name] for name in attack_cfg.success.loot]
    action_params["success"] = CppAttackOutcome(success_actor, success_target, success_loot)
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

    # --- Territories ---

    if game_config.territories:
        game_cpp_params["territories"] = _convert_game_territory_configs(
            game_config.territories, id_maps, territory_name_to_index
        )
    # --- Events ---

    if game_config.events:
        game_cpp_params["events"] = _convert_event_configs(game_config.events, id_maps)

    # --- Materialized queries ---

    materialized_queries_cpp = []
    for mq in game_config.materialize_queries:
        cpp_mq = CppMaterializedQueryTag()
        cpp_mq.tag_id = tag_name_to_id[mq.tag]
        cpp_mq.set_query(_convert_tag_query(mq.query, id_maps, f"materialized_query '{mq.tag}'"))
        materialized_queries_cpp.append(cpp_mq)
    if materialized_queries_cpp:
        game_cpp_params["materialized_queries"] = materialized_queries_cpp

    # --- Game-level on_tick handlers ---

    if game_config.on_tick:
        game_cpp_params["on_tick"] = _convert_handlers(game_config.on_tick, id_maps)

    return CppGameConfig(**game_cpp_params), agent_renames
