"""Shared mutation conversion utilities for Python-to-C++ config conversion."""

from __future__ import annotations

from typing import TYPE_CHECKING

from mettagrid.config.game_value import val
from mettagrid.config.mettagrid_c_value_config import resolve_game_value
from mettagrid.config.mutation import (
    AddTagMutation,
    ChangeVibeMutation,
    ClearInventoryMutation,
    EntityTarget,
    QueryInventoryMutation,
    RaycastSpawnMutation,
    RecomputeMaterializedQueryMutation,
    RelocateMutation,
    RemoveTagMutation,
    RemoveTagsWithPrefixMutation,
    ResourceDeltaMutation,
    ResourceTransferMutation,
    SetGameValueMutation,
    SpawnObjectMutation,
    StatsEntity,
    StatsMutation,
    StatsTarget,
    SwapMutation,
    UseTargetMutation,
)
from mettagrid.mettagrid_c import AddTagMutationConfig as CppAddTagMutationConfig
from mettagrid.mettagrid_c import ChangeVibeMutationConfig as CppChangeVibeMutationConfig
from mettagrid.mettagrid_c import ClearInventoryMutationConfig as CppClearInventoryMutationConfig
from mettagrid.mettagrid_c import EntityRef as CppEntityRef
from mettagrid.mettagrid_c import GameValueMutationConfig as CppGameValueMutationConfig
from mettagrid.mettagrid_c import QueryInventoryMutationConfig as CppQueryInventoryMutationConfig
from mettagrid.mettagrid_c import RaycastSpawnMutationConfig as CppRaycastSpawnMutationConfig
from mettagrid.mettagrid_c import (
    RecomputeMaterializedQueryMutationConfig as CppRecomputeMaterializedQueryMutationConfig,
)
from mettagrid.mettagrid_c import RelocateMutationConfig as CppRelocateMutationConfig
from mettagrid.mettagrid_c import RemoveTagMutationConfig as CppRemoveTagMutationConfig
from mettagrid.mettagrid_c import RemoveTagsWithPrefixMutationConfig as CppRemoveTagsWithPrefixMutationConfig
from mettagrid.mettagrid_c import ResourceDeltaMutationConfig as CppResourceDeltaMutationConfig
from mettagrid.mettagrid_c import ResourceTransferMutationConfig as CppResourceTransferMutationConfig
from mettagrid.mettagrid_c import SpawnObjectMutationConfig as CppSpawnObjectMutationConfig
from mettagrid.mettagrid_c import StatsEntity as CppStatsEntity
from mettagrid.mettagrid_c import StatsMutationConfig as CppStatsMutationConfig
from mettagrid.mettagrid_c import StatsTarget as CppStatsTarget
from mettagrid.mettagrid_c import SwapMutationConfig as CppSwapMutationConfig
from mettagrid.mettagrid_c import UseTargetMutationConfig as CppUseTargetMutationConfig

if TYPE_CHECKING:
    from mettagrid.config.cpp_id_maps import CppIdMaps

_ENTITY_TARGET_TO_CPP: dict[EntityTarget, CppEntityRef] = {
    EntityTarget.ACTOR: CppEntityRef.actor,
    EntityTarget.TARGET: CppEntityRef.target,
}

_STATS_TARGET_TO_CPP: dict[StatsTarget, CppStatsTarget] = {
    StatsTarget.GAME: CppStatsTarget.game,
    StatsTarget.AGENT: CppStatsTarget.agent,
}

_STATS_ENTITY_TO_CPP: dict[StatsEntity, CppStatsEntity] = {
    StatsEntity.TARGET: CppStatsEntity.target,
    StatsEntity.ACTOR: CppStatsEntity.actor,
}


_DIR_MAP = {"north": (-1, 0), "south": (1, 0), "east": (0, 1), "west": (0, -1)}


def _convert_raycast_spawn_mutation(mutation, target_obj, id_maps):
    """Convert RaycastSpawnMutation — deferred import to avoid circular dependency."""
    from mettagrid.config.mettagrid_c_config import _attach, _convert_one_filter  # noqa: PLC0415

    cpp_mutation = CppRaycastSpawnMutationConfig()
    cpp_mutation.object_type = mutation.object_type
    cpp_mutation.max_range = mutation.max_range
    cpp_mutation.directions = [_DIR_MAP[d] for d in mutation.directions]
    for blocker_filter in mutation.blocker:
        result = _convert_one_filter(blocker_filter, id_maps, context="raycast_spawn blocker")
        assert result is not None, f"Failed to convert blocker filter: {blocker_filter}"
        _type_key, cpp_blocker = result
        _attach(cpp_mutation, _type_key, cpp_blocker, method_prefix="blocker_")
    target_obj.add_raycast_spawn_mutation(cpp_mutation)


def convert_entity_ref(target: EntityTarget) -> CppEntityRef:
    assert target in _ENTITY_TARGET_TO_CPP, f"Unknown EntityTarget: {target}"
    return _ENTITY_TARGET_TO_CPP[target]


def convert_mutations(
    mutations: list,
    target_obj,
    id_maps: CppIdMaps,
    context: str = "",
) -> None:
    """Convert Python mutations and add them to a C++ config object."""
    for mutation in mutations:
        if isinstance(mutation, ResourceDeltaMutation):
            for resource_name, delta in mutation.deltas.items():
                assert resource_name in id_maps.resource_name_to_id, (
                    f"ResourceDeltaMutation references unknown resource '{resource_name}'. "
                    f"Available resources: {list(id_maps.resource_name_to_id.keys())}"
                )
                cpp_mutation = CppResourceDeltaMutationConfig(
                    entity=convert_entity_ref(mutation.target),
                    resource_id=id_maps.resource_name_to_id[resource_name],
                    delta=delta,
                )
                target_obj.add_resource_delta_mutation(cpp_mutation)

        elif isinstance(mutation, ResourceTransferMutation):
            for resource_name, amount in mutation.resources.items():
                assert resource_name in id_maps.resource_name_to_id, (
                    f"ResourceTransferMutation references unknown resource '{resource_name}'. "
                    f"Available resources: {list(id_maps.resource_name_to_id.keys())}"
                )
                cpp_mutation = CppResourceTransferMutationConfig(
                    source=convert_entity_ref(mutation.from_target),
                    destination=convert_entity_ref(mutation.to_target),
                    resource_id=id_maps.resource_name_to_id[resource_name],
                    amount=amount,
                    remove_source_when_empty=mutation.remove_source_when_empty,
                )
                target_obj.add_resource_transfer_mutation(cpp_mutation)

        elif isinstance(mutation, ClearInventoryMutation):
            limit_name = mutation.limit_name
            if limit_name not in id_maps.limit_name_to_resource_ids:
                ctx_msg = f" in {context}" if context else ""
                raise ValueError(
                    f"ClearInventoryMutation{ctx_msg} references unknown limit_name '{limit_name}'. "
                    f"Available limits: {list(id_maps.limit_name_to_resource_ids.keys())}"
                )
            cpp_mutation = CppClearInventoryMutationConfig(
                entity=convert_entity_ref(mutation.target),
                resource_ids=id_maps.limit_name_to_resource_ids[limit_name],
            )
            target_obj.add_clear_inventory_mutation(cpp_mutation)

        elif isinstance(mutation, StatsMutation):
            cpp_mutation = CppStatsMutationConfig(
                stat_name=mutation.stat,
                target=_STATS_TARGET_TO_CPP[mutation.target],
                entity=_STATS_ENTITY_TO_CPP[mutation.entity],
            )
            cpp_mutation.source = resolve_game_value(mutation.source, id_maps)
            target_obj.add_stats_mutation(cpp_mutation)

        elif isinstance(mutation, AddTagMutation):
            assert mutation.tag in id_maps.tag_name_to_id, (
                f"AddTagMutation references unknown tag '{mutation.tag}'. "
                f"Available tags: {list(id_maps.tag_name_to_id.keys())}"
            )
            cpp_mutation = CppAddTagMutationConfig(
                entity=convert_entity_ref(mutation.target),
                tag_id=id_maps.tag_name_to_id[mutation.tag],
            )
            target_obj.add_add_tag_mutation(cpp_mutation)

        elif isinstance(mutation, ChangeVibeMutation):
            vibe_id = id_maps.vibe_name_to_id.get(mutation.vibe_name, 0)
            cpp_mutation = CppChangeVibeMutationConfig(
                entity=convert_entity_ref(mutation.target),
                vibe_id=vibe_id,
            )
            target_obj.add_change_vibe_mutation(cpp_mutation)

        elif isinstance(mutation, RemoveTagMutation):
            assert mutation.tag in id_maps.tag_name_to_id, (
                f"RemoveTagMutation references unknown tag '{mutation.tag}'. "
                f"Available tags: {list(id_maps.tag_name_to_id.keys())}"
            )
            cpp_mutation = CppRemoveTagMutationConfig(
                entity=convert_entity_ref(mutation.target),
                tag_id=id_maps.tag_name_to_id[mutation.tag],
            )
            target_obj.add_remove_tag_mutation(cpp_mutation)

        elif isinstance(mutation, RemoveTagsWithPrefixMutation):
            matching_tag_ids = [
                tag_id for name, tag_id in id_maps.tag_name_to_id.items() if name.startswith(mutation.prefix)
            ]
            cpp_mutation = CppRemoveTagsWithPrefixMutationConfig(
                entity=convert_entity_ref(mutation.target),
                tag_ids=matching_tag_ids,
            )
            target_obj.add_remove_tags_with_prefix_mutation(cpp_mutation)

        elif isinstance(mutation, SetGameValueMutation):
            cpp_gv_cfg = resolve_game_value(mutation.value, id_maps)
            source = mutation.source if mutation.source is not None else val(mutation.delta)
            cpp_source_cfg = resolve_game_value(source, id_maps)
            cpp_mutation = CppGameValueMutationConfig(
                value=cpp_gv_cfg,
                target=convert_entity_ref(mutation.target),
                source=cpp_source_cfg,
            )
            target_obj.add_game_value_mutation(cpp_mutation)

        elif isinstance(mutation, RecomputeMaterializedQueryMutation):
            matching_tag_ids = [
                tag_id for name, tag_id in id_maps.tag_name_to_id.items() if name.startswith(mutation.tag_prefix)
            ]
            assert matching_tag_ids, (
                f"RecomputeMaterializedQueryMutation prefix '{mutation.tag_prefix}' matched no tags. "
                f"Available tags: {list(id_maps.tag_name_to_id.keys())}"
            )
            for tag_id in matching_tag_ids:
                cpp_mutation = CppRecomputeMaterializedQueryMutationConfig()
                cpp_mutation.tag_id = tag_id
                target_obj.add_recompute_materialized_query_mutation(cpp_mutation)

        elif isinstance(mutation, QueryInventoryMutation):
            from mettagrid.config.mettagrid_c_config import _convert_tag_query  # noqa: PLC0415

            cpp_query = _convert_tag_query(
                mutation.query,
                id_maps,
                context=f"{context} query_inventory mutation",
            )
            cpp_mutation = CppQueryInventoryMutationConfig()
            cpp_mutation.set_query(cpp_query)
            for rname in mutation.deltas:
                assert rname in id_maps.resource_name_to_id, (
                    f"QueryInventoryMutation in {context} references unknown resource '{rname}'. "
                    f"Available resources: {list(id_maps.resource_name_to_id.keys())}"
                )
            cpp_mutation.deltas = [
                (id_maps.resource_name_to_id[rname], delta) for rname, delta in mutation.deltas.items()
            ]
            if mutation.source is not None:
                cpp_mutation.source = convert_entity_ref(mutation.source)
                cpp_mutation.has_source = True
            if mutation.transfer_stats:
                cpp_mutation.transfer_stat_names = [
                    (id_maps.resource_name_to_id[rname], stat_name)
                    for rname, stat_name in mutation.transfer_stats.items()
                ]
            target_obj.add_query_inventory_mutation(cpp_mutation)

        elif isinstance(mutation, SpawnObjectMutation):
            cpp_mutation = CppSpawnObjectMutationConfig()
            cpp_mutation.object_type = mutation.object_type
            target_obj.add_spawn_object_mutation(cpp_mutation)

        elif isinstance(mutation, RelocateMutation):
            target_obj.add_relocate_mutation(CppRelocateMutationConfig())

        elif isinstance(mutation, SwapMutation):
            target_obj.add_swap_mutation(CppSwapMutationConfig())

        elif isinstance(mutation, UseTargetMutation):
            target_obj.add_use_target_mutation(CppUseTargetMutationConfig())

        elif isinstance(mutation, RaycastSpawnMutation):
            _convert_raycast_spawn_mutation(mutation, target_obj, id_maps)
