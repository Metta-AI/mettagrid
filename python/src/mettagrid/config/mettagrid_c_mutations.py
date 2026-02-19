"""Shared mutation conversion utilities for Python-to-C++ config conversion."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
    RecomputeMaterializedQueryMutation,
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
from mettagrid.mettagrid_c import (
    RecomputeMaterializedQueryMutationConfig as CppRecomputeMaterializedQueryMutationConfig,
)
from mettagrid.mettagrid_c import RemoveTagMutationConfig as CppRemoveTagMutationConfig
from mettagrid.mettagrid_c import RemoveTagsWithPrefixMutationConfig as CppRemoveTagsWithPrefixMutationConfig
from mettagrid.mettagrid_c import ResourceDeltaMutationConfig as CppResourceDeltaMutationConfig
from mettagrid.mettagrid_c import ResourceTransferMutationConfig as CppResourceTransferMutationConfig
from mettagrid.mettagrid_c import StatsEntity as CppStatsEntity
from mettagrid.mettagrid_c import StatsMutationConfig as CppStatsMutationConfig
from mettagrid.mettagrid_c import StatsTarget as CppStatsTarget

if TYPE_CHECKING:
    from mettagrid.config.cpp_id_maps import CppIdMaps

_ENTITY_TARGET_TO_CPP: dict[EntityTarget, CppEntityRef] = {
    EntityTarget.ACTOR: CppEntityRef.actor,
    EntityTarget.TARGET: CppEntityRef.target,
    EntityTarget.ACTOR_COLLECTIVE: CppEntityRef.actor_collective,
    EntityTarget.TARGET_COLLECTIVE: CppEntityRef.target_collective,
}

_ALIGN_TO_CPP: dict[AlignTo, CppAlignTo] = {
    AlignTo.ACTOR_COLLECTIVE: CppAlignTo.actor_collective,
    AlignTo.NONE: CppAlignTo.none,
}

_STATS_TARGET_TO_CPP: dict[StatsTarget, CppStatsTarget] = {
    StatsTarget.GAME: CppStatsTarget.game,
    StatsTarget.AGENT: CppStatsTarget.agent,
    StatsTarget.COLLECTIVE: CppStatsTarget.collective,
}

_STATS_ENTITY_TO_CPP: dict[StatsEntity, CppStatsEntity] = {
    StatsEntity.TARGET: CppStatsEntity.target,
    StatsEntity.ACTOR: CppStatsEntity.actor,
}


def convert_entity_ref(target: EntityTarget) -> CppEntityRef:
    assert target in _ENTITY_TARGET_TO_CPP, f"Unknown EntityTarget: {target}"
    return _ENTITY_TARGET_TO_CPP[target]


def convert_align_to(align_to: AlignTo) -> CppAlignTo:
    assert align_to in _ALIGN_TO_CPP, f"Unknown AlignTo: {align_to}"
    return _ALIGN_TO_CPP[align_to]


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

        elif isinstance(mutation, AlignmentMutation):
            cpp_mutation = CppAlignmentMutationConfig(
                align_to=convert_align_to(mutation.align_to),
            )
            target_obj.add_alignment_mutation(cpp_mutation)

        elif isinstance(mutation, FreezeMutation):
            cpp_mutation = CppFreezeMutationConfig(duration=mutation.duration)
            target_obj.add_freeze_mutation(cpp_mutation)

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
                delta=mutation.delta,
                target=_STATS_TARGET_TO_CPP[mutation.target],
                entity=_STATS_ENTITY_TO_CPP[mutation.entity],
            )
            target_obj.add_stats_mutation(cpp_mutation)

        elif isinstance(mutation, AddTagMutation):
            tag_key = mutation.tag.name
            assert tag_key in id_maps.tag_name_to_id, (
                f"AddTagMutation references unknown tag '{tag_key}'. "
                f"Available tags: {list(id_maps.tag_name_to_id.keys())}"
            )
            cpp_mutation = CppAddTagMutationConfig(
                entity=convert_entity_ref(mutation.target),
                tag_id=id_maps.tag_name_to_id[tag_key],
            )
            target_obj.add_add_tag_mutation(cpp_mutation)

        elif isinstance(mutation, RemoveTagMutation):
            tag_key = mutation.tag.name
            assert tag_key in id_maps.tag_name_to_id, (
                f"RemoveTagMutation references unknown tag '{tag_key}'. "
                f"Available tags: {list(id_maps.tag_name_to_id.keys())}"
            )
            cpp_mutation = CppRemoveTagMutationConfig(
                entity=convert_entity_ref(mutation.target),
                tag_id=id_maps.tag_name_to_id[tag_key],
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
            source = mutation.source if mutation.source is not None else ConstValue(value=float(mutation.delta))
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
            target_obj.add_query_inventory_mutation(cpp_mutation)
