"""Shared mutation conversion utilities for Python-to-C++ config conversion."""

from mettagrid.config.mutation import (
    AddTagMutation,
    AlignmentEntityTarget,
    AlignmentMutation,
    AlignTo,
    ClearInventoryMutation,
    EntityTarget,
    FreezeMutation,
    RemoveTagMutation,
    ResourceDeltaMutation,
    ResourceTransferMutation,
    StatsMutation,
    StatsTarget,
)
from mettagrid.mettagrid_c import AddTagMutationConfig as CppAddTagMutationConfig
from mettagrid.mettagrid_c import AlignmentMutationConfig as CppAlignmentMutationConfig
from mettagrid.mettagrid_c import AlignTo as CppAlignTo
from mettagrid.mettagrid_c import ClearInventoryMutationConfig as CppClearInventoryMutationConfig
from mettagrid.mettagrid_c import EntityRef as CppEntityRef
from mettagrid.mettagrid_c import FreezeMutationConfig as CppFreezeMutationConfig
from mettagrid.mettagrid_c import RemoveTagMutationConfig as CppRemoveTagMutationConfig
from mettagrid.mettagrid_c import ResourceDeltaMutationConfig as CppResourceDeltaMutationConfig
from mettagrid.mettagrid_c import ResourceTransferMutationConfig as CppResourceTransferMutationConfig
from mettagrid.mettagrid_c import StatsMutationConfig as CppStatsMutationConfig
from mettagrid.mettagrid_c import StatsTarget as CppStatsTarget

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

# Mapping from Python AlignmentEntityTarget enum to C++ EntityRef enum
_ALIGNMENT_ENTITY_TARGET_TO_CPP: dict[AlignmentEntityTarget, CppEntityRef] = {
    AlignmentEntityTarget.ACTOR: CppEntityRef.actor,
    AlignmentEntityTarget.TARGET: CppEntityRef.target,
}


def convert_entity_ref(target: EntityTarget) -> CppEntityRef:
    """Convert Python EntityTarget enum to C++ EntityRef enum.

    Args:
        target: EntityTarget enum value

    Returns:
        Corresponding C++ EntityRef enum value
    """
    return _ENTITY_TARGET_TO_CPP.get(target, CppEntityRef.target)


def convert_align_to(align_to: AlignTo) -> CppAlignTo:
    """Convert Python AlignTo enum to C++ AlignTo enum.

    Args:
        align_to: AlignTo enum value

    Returns:
        Corresponding C++ AlignTo enum value
    """
    return _ALIGN_TO_CPP.get(align_to, CppAlignTo.none)


def convert_mutations(
    mutations: list,
    target_obj,
    resource_name_to_id: dict[str, int],
    limit_name_to_resource_ids: dict[str, list[int]],
    tag_name_to_id: dict[str, int],
    context: str = "",
) -> None:
    """Convert Python mutations and add them to a C++ config object.

    Args:
        mutations: List of Python mutation configs (AnyMutation)
        target_obj: C++ config object with add_*_mutation methods (e.g., CppHandlerConfig)
        resource_name_to_id: Dict mapping resource names to IDs
        limit_name_to_resource_ids: Dict mapping limit names to lists of resource IDs
        tag_name_to_id: Dict mapping tag names to IDs
        context: Description for error messages (e.g., "handler 'foo'")
    """
    for mutation in mutations:
        if isinstance(mutation, ResourceDeltaMutation):
            # Resource delta mutation can have multiple deltas - add one mutation per resource
            for resource_name, delta in mutation.deltas.items():
                assert resource_name in resource_name_to_id, (
                    f"ResourceDeltaMutation in {context} references unknown resource '{resource_name}'"
                )
                cpp_mutation = CppResourceDeltaMutationConfig(
                    convert_entity_ref(mutation.target), resource_name_to_id[resource_name], delta
                )
                target_obj.add_resource_delta_mutation(cpp_mutation)

        elif isinstance(mutation, ResourceTransferMutation):
            # Resource transfer mutation can have multiple resources - add one mutation per resource
            for resource_name, amount in mutation.resources.items():
                assert resource_name in resource_name_to_id, (
                    f"ResourceTransferMutation in {context} references unknown resource '{resource_name}'"
                )
                cpp_mutation = CppResourceTransferMutationConfig(
                    convert_entity_ref(mutation.from_target),
                    convert_entity_ref(mutation.to_target),
                    resource_name_to_id[resource_name],
                    amount,
                )
                target_obj.add_resource_transfer_mutation(cpp_mutation)

        elif isinstance(mutation, AlignmentMutation):
            cpp_mutation = CppAlignmentMutationConfig(convert_align_to(mutation.align_to))
            target_obj.add_alignment_mutation(cpp_mutation)

        elif isinstance(mutation, FreezeMutation):
            cpp_mutation = CppFreezeMutationConfig(mutation.duration)
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
                convert_entity_ref(mutation.target), limit_name_to_resource_ids[limit_name]
            )
            target_obj.add_clear_inventory_mutation(cpp_mutation)

        elif isinstance(mutation, StatsMutation):
            cpp_mutation = CppStatsMutationConfig(
                mutation.stat, mutation.delta, _STATS_TARGET_TO_CPP.get(mutation.target, CppStatsTarget.collective)
            )
            target_obj.add_stats_mutation(cpp_mutation)

        elif isinstance(mutation, AddTagMutation):
            assert mutation.tag in tag_name_to_id, (
                f"AddTagMutation in {context} references unknown tag '{mutation.tag}'. "
                f"Add it to GameConfig.tags or object tags."
            )
            cpp_mutation = CppAddTagMutationConfig(
                _ALIGNMENT_ENTITY_TARGET_TO_CPP.get(mutation.target, CppEntityRef.target),
                tag_name_to_id[mutation.tag],
            )
            target_obj.add_add_tag_mutation(cpp_mutation)

        elif isinstance(mutation, RemoveTagMutation):
            assert mutation.tag in tag_name_to_id, (
                f"RemoveTagMutation in {context} references unknown tag '{mutation.tag}'. "
                f"Add it to GameConfig.tags or object tags."
            )
            cpp_mutation = CppRemoveTagMutationConfig(
                _ALIGNMENT_ENTITY_TARGET_TO_CPP.get(mutation.target, CppEntityRef.target),
                tag_name_to_id[mutation.tag],
            )
            target_obj.add_remove_tag_mutation(cpp_mutation)
