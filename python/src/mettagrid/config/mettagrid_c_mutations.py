"""Shared mutation conversion utilities for Python-to-C++ config conversion."""

from mettagrid.config.game_value import ConstValue
from mettagrid.config.mettagrid_c_value_config import resolve_game_value
from mettagrid.config.mutation import (
    AddTagMutation,
    AlignmentMutation,
    AlignTo,
    ClearInventoryMutation,
    EntityTarget,
    FreezeMutation,
    QueryInventoryMutation,
    RecomputeQueryTagMutation,
    RemoveTagMutation,
    RemoveTagsWithPrefixMutation,
    ResourceDeltaMutation,
    ResourceTransferMutation,
    SetGameValueMutation,
    StatsEntity,
    StatsMutation,
    StatsTarget,
)
from mettagrid.mettagrid_c import AddTagMutationConfig as CppAddTagMutationConfig
from mettagrid.mettagrid_c import AlignmentMutationConfig as CppAlignmentMutationConfig
from mettagrid.mettagrid_c import AlignTo as CppAlignTo
from mettagrid.mettagrid_c import ClearInventoryMutationConfig as CppClearInventoryMutationConfig
from mettagrid.mettagrid_c import EntityRef as CppEntityRef
from mettagrid.mettagrid_c import FreezeMutationConfig as CppFreezeMutationConfig
from mettagrid.mettagrid_c import GameValueMutationConfig as CppGameValueMutationConfig
from mettagrid.mettagrid_c import QueryInventoryMutationConfig as CppQueryInventoryMutationConfig
from mettagrid.mettagrid_c import RecomputeQueryTagMutationConfig as CppRecomputeQueryTagMutationConfig
from mettagrid.mettagrid_c import RemoveTagMutationConfig as CppRemoveTagMutationConfig
from mettagrid.mettagrid_c import RemoveTagsWithPrefixMutationConfig as CppRemoveTagsWithPrefixMutationConfig
from mettagrid.mettagrid_c import ResourceDeltaMutationConfig as CppResourceDeltaMutationConfig
from mettagrid.mettagrid_c import ResourceTransferMutationConfig as CppResourceTransferMutationConfig
from mettagrid.mettagrid_c import StatsEntity as CppStatsEntity
from mettagrid.mettagrid_c import StatsMutationConfig as CppStatsMutationConfig
from mettagrid.mettagrid_c import StatsTarget as CppStatsTarget
from mettagrid.mettagrid_c import TagQueryConfig as CppTagQueryConfig
from mettagrid.mettagrid_c import make_query_config

# Mapping from Python EntityTarget enum to C++ EntityRef enum
_ENTITY_TARGET_TO_CPP: dict[EntityTarget, CppEntityRef] = {
    EntityTarget.ACTOR: CppEntityRef.actor,
    EntityTarget.TARGET: CppEntityRef.target,
    EntityTarget.ACTOR_COLLECTIVE: CppEntityRef.actor_collective,
    EntityTarget.TARGET_COLLECTIVE: CppEntityRef.target_collective,
}

# Mapping from Python AlignTo enum to C++ AlignTo enum
_ALIGN_TO_CPP: dict[AlignTo, CppAlignTo] = {
    AlignTo.ACTOR_COLLECTIVE: CppAlignTo.actor_collective,
    AlignTo.NONE: CppAlignTo.none,
}

# Mapping from Python StatsTarget enum to C++ StatsTarget enum
_STATS_TARGET_TO_CPP: dict[StatsTarget, CppStatsTarget] = {
    StatsTarget.GAME: CppStatsTarget.game,
    StatsTarget.AGENT: CppStatsTarget.agent,
    StatsTarget.COLLECTIVE: CppStatsTarget.collective,
}

# Mapping from Python StatsEntity enum to C++ StatsEntity enum
_STATS_ENTITY_TO_CPP: dict[StatsEntity, CppStatsEntity] = {
    StatsEntity.TARGET: CppStatsEntity.target,
    StatsEntity.ACTOR: CppStatsEntity.actor,
}


def convert_entity_ref(target: EntityTarget) -> CppEntityRef:
    """Convert Python EntityTarget enum to C++ EntityRef enum.

    Args:
        target: EntityTarget enum value

    Returns:
        Corresponding C++ EntityRef enum value
    """
    assert target in _ENTITY_TARGET_TO_CPP, f"Unknown EntityTarget: {target}"
    return _ENTITY_TARGET_TO_CPP[target]


def convert_align_to(align_to: AlignTo) -> CppAlignTo:
    """Convert Python AlignTo enum to C++ AlignTo enum.

    Args:
        align_to: AlignTo enum value

    Returns:
        Corresponding C++ AlignTo enum value
    """
    assert align_to in _ALIGN_TO_CPP, f"Unknown AlignTo: {align_to}"
    return _ALIGN_TO_CPP[align_to]


def _convert_query_for_mutation(query, tag_name_to_id, resource_name_to_id, vibe_name_to_id, context=""):
    """Convert a Python Query to a C++ QueryConfigHolder for use in mutations.

    Uses the same TagQueryConfig + filter conversion as proximity filters.
    """
    from mettagrid.config.mettagrid_c_config import _convert_filters  # noqa: PLC0415

    query_tag = query.tag.name
    assert query_tag in tag_name_to_id, (
        f"Query in {context} references unknown tag '{query_tag}'. Available tags: {list(tag_name_to_id.keys())}"
    )
    tag_query = CppTagQueryConfig()
    tag_query.tag_id = tag_name_to_id[query_tag]

    _convert_filters(
        query.filters,
        tag_query,
        resource_name_to_id,
        vibe_name_to_id,
        tag_name_to_id,
        context=context,
    )

    return make_query_config(tag_query)


def convert_mutations(
    mutations: list,
    target_obj,
    resource_name_to_id: dict[str, int],
    limit_name_to_resource_ids: dict[str, list[int]],
    tag_name_to_id: dict[str, int],
    vibe_name_to_id: dict[str, int],
    context: str = "",
) -> None:
    """Convert Python mutations and add them to a C++ config object.

    Args:
        mutations: List of Python mutation configs (AnyMutation)
        target_obj: C++ config object with add_*_mutation methods (e.g., CppHandlerConfig)
        resource_name_to_id: Dict mapping resource names to IDs
        limit_name_to_resource_ids: Dict mapping limit names to lists of resource IDs
        tag_name_to_id: Dict mapping tag names to IDs
        vibe_name_to_id: Dict mapping vibe names to IDs
        context: Description for error messages (e.g., "handler 'foo'")
    """
    for mutation in mutations:
        if isinstance(mutation, ResourceDeltaMutation):
            # Resource delta mutation can have multiple deltas - add one mutation per resource
            for resource_name, delta in mutation.deltas.items():
                assert resource_name in resource_name_to_id, (
                    f"ResourceDeltaMutation references unknown resource '{resource_name}'. "
                    f"Available resources: {list(resource_name_to_id.keys())}"
                )
                cpp_mutation = CppResourceDeltaMutationConfig(
                    entity=convert_entity_ref(mutation.target),
                    resource_id=resource_name_to_id[resource_name],
                    delta=delta,
                )
                target_obj.add_resource_delta_mutation(cpp_mutation)

        elif isinstance(mutation, ResourceTransferMutation):
            # Resource transfer mutation can have multiple resources - add one mutation per resource
            for resource_name, amount in mutation.resources.items():
                assert resource_name in resource_name_to_id, (
                    f"ResourceTransferMutation references unknown resource '{resource_name}'. "
                    f"Available resources: {list(resource_name_to_id.keys())}"
                )
                cpp_mutation = CppResourceTransferMutationConfig(
                    source=convert_entity_ref(mutation.from_target),
                    destination=convert_entity_ref(mutation.to_target),
                    resource_id=resource_name_to_id[resource_name],
                    amount=amount,
                    remove_source_when_empty=mutation.remove_source_when_empty,
                )
                target_obj.add_resource_transfer_mutation(cpp_mutation)

        elif isinstance(mutation, AlignmentMutation):
            cpp_mutation = CppAlignmentMutationConfig(
                align_to=convert_align_to(mutation.align_to),
            )
            target_obj.add_alignment_mutation(cpp_mutation)

        elif isinstance(mutation, FreezeMutation):
            cpp_mutation = CppFreezeMutationConfig(
                duration=mutation.duration,
            )
            target_obj.add_freeze_mutation(cpp_mutation)

        elif isinstance(mutation, ClearInventoryMutation):
            limit_name = mutation.limit_name
            if limit_name not in limit_name_to_resource_ids:
                ctx_msg = f" in {context}" if context else ""
                raise ValueError(
                    f"ClearInventoryMutation{ctx_msg} references unknown limit_name '{limit_name}'. "
                    f"Available limits: {list(limit_name_to_resource_ids.keys())}"
                )
            cpp_mutation = CppClearInventoryMutationConfig(
                entity=convert_entity_ref(mutation.target),
                resource_ids=limit_name_to_resource_ids[limit_name],
            )
            target_obj.add_clear_inventory_mutation(cpp_mutation)

        elif isinstance(mutation, StatsMutation):
            cpp_mutation = CppStatsMutationConfig(
                stat_name=mutation.stat,
                delta=mutation.delta,
                target=_STATS_TARGET_TO_CPP[mutation.target],
                entity=_STATS_ENTITY_TO_CPP[mutation.entity],
            )
            target_obj.add_stats_mutation(cpp_mutation)

        elif isinstance(mutation, AddTagMutation):
            tag_key = mutation.tag.name
            assert tag_key in tag_name_to_id, (
                f"AddTagMutation references unknown tag '{tag_key}'. Available tags: {list(tag_name_to_id.keys())}"
            )
            cpp_mutation = CppAddTagMutationConfig(
                entity=convert_entity_ref(mutation.target),
                tag_id=tag_name_to_id[tag_key],
            )
            target_obj.add_add_tag_mutation(cpp_mutation)

        elif isinstance(mutation, RemoveTagMutation):
            tag_key = mutation.tag.name
            assert tag_key in tag_name_to_id, (
                f"RemoveTagMutation references unknown tag '{tag_key}'. Available tags: {list(tag_name_to_id.keys())}"
            )
            cpp_mutation = CppRemoveTagMutationConfig(
                entity=convert_entity_ref(mutation.target),
                tag_id=tag_name_to_id[tag_key],
            )
            target_obj.add_remove_tag_mutation(cpp_mutation)

        elif isinstance(mutation, RemoveTagsWithPrefixMutation):
            matching_tag_ids = [tag_id for name, tag_id in tag_name_to_id.items() if name.startswith(mutation.prefix)]
            cpp_mutation = CppRemoveTagsWithPrefixMutationConfig(
                entity=convert_entity_ref(mutation.target),
                tag_ids=matching_tag_ids,
            )
            target_obj.add_remove_tags_with_prefix_mutation(cpp_mutation)

        elif isinstance(mutation, SetGameValueMutation):
            mappings = {
                "resource_name_to_id": resource_name_to_id,
                "stat_name_to_id": {},  # Stat IDs resolved at C++ init time
                "tag_name_to_id": tag_name_to_id,
            }
            cpp_gv_cfg = resolve_game_value(mutation.value, mappings)

            # Resolve source: if explicit source provided, use it; otherwise wrap delta as ConstValue
            source = mutation.source if mutation.source is not None else ConstValue(value=float(mutation.delta))
            cpp_source_cfg = resolve_game_value(source, mappings)

            cpp_mutation = CppGameValueMutationConfig(
                value=cpp_gv_cfg,
                target=convert_entity_ref(mutation.target),
                source=cpp_source_cfg,
            )
            target_obj.add_game_value_mutation(cpp_mutation)

        elif isinstance(mutation, RecomputeQueryTagMutation):
            matching_tag_ids = [
                tag_id for name, tag_id in tag_name_to_id.items() if name.startswith(mutation.tag_prefix)
            ]
            assert matching_tag_ids, (
                f"RecomputeQueryTagMutation prefix '{mutation.tag_prefix}' matched no tags. "
                f"Available tags: {list(tag_name_to_id.keys())}"
            )
            for tag_id in matching_tag_ids:
                cpp_mutation = CppRecomputeQueryTagMutationConfig()
                cpp_mutation.tag_id = tag_id
                target_obj.add_recompute_query_tag_mutation(cpp_mutation)

        elif isinstance(mutation, QueryInventoryMutation):
            cpp_query = _convert_query_for_mutation(
                mutation.query,
                tag_name_to_id,
                resource_name_to_id,
                vibe_name_to_id,
                context=f"{context} query_inventory mutation",
            )
            cpp_mutation = CppQueryInventoryMutationConfig()
            cpp_mutation.set_query(cpp_query)
            for rname in mutation.deltas:
                assert rname in resource_name_to_id, (
                    f"QueryInventoryMutation in {context} references unknown resource '{rname}'. "
                    f"Available resources: {list(resource_name_to_id.keys())}"
                )
            cpp_mutation.deltas = [(resource_name_to_id[rname], delta) for rname, delta in mutation.deltas.items()]
            if mutation.source is not None:
                cpp_mutation.source = convert_entity_ref(mutation.source)
                cpp_mutation.has_source = True
            target_obj.add_query_inventory_mutation(cpp_mutation)
