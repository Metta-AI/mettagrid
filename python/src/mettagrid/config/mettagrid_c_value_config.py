"""Convert Python GameValue types to C++ GameValueConfig variants."""

from __future__ import annotations

from typing import TYPE_CHECKING

from mettagrid.config.game_value import (
    ConstValue,
    GameValue,
    InventoryValue,
    NumObjectsValue,
    QueryInventoryValue,
    Scope,
    StatValue,
    TagCountValue,
)
from mettagrid.config.tag import typeTag
from mettagrid.mettagrid_c import ConstValueConfig as CppConstValueConfig
from mettagrid.mettagrid_c import GameValueScope
from mettagrid.mettagrid_c import InventoryValueConfig as CppInventoryValueConfig
from mettagrid.mettagrid_c import QueryInventoryValueConfig as CppQueryInventoryValueConfig
from mettagrid.mettagrid_c import StatValueConfig as CppStatValueConfig
from mettagrid.mettagrid_c import TagCountValueConfig as CppTagCountValueConfig

if TYPE_CHECKING:
    from mettagrid.config.cpp_id_maps import CppIdMaps


def resolve_game_value(gv: GameValue, id_maps: CppIdMaps):
    """Convert a Python GameValue to a C++ typed GameValueConfig variant."""
    if isinstance(gv, InventoryValue):
        cfg = CppInventoryValueConfig()
        cfg.scope = _convert_scope(gv.scope)
        cfg.id = id_maps.resource_name_to_id[gv.item]
        return cfg

    if isinstance(gv, StatValue):
        cfg = CppStatValueConfig()
        cfg.scope = _convert_scope(gv.scope)
        cfg.stat_name = gv.name
        cfg.delta = gv.delta
        return cfg

    if isinstance(gv, NumObjectsValue):
        cfg = CppTagCountValueConfig()
        tag_name = typeTag(gv.object_type)
        cfg.id = id_maps.tag_name_to_id[tag_name]
        return cfg

    if isinstance(gv, TagCountValue):
        cfg = CppTagCountValueConfig()
        cfg.id = id_maps.tag_name_to_id[gv.tag]
        return cfg

    if isinstance(gv, ConstValue):
        cfg = CppConstValueConfig()
        cfg.value = gv.value
        return cfg

    if isinstance(gv, QueryInventoryValue):
        from mettagrid.config.mettagrid_c_config import _convert_tag_query  # noqa: PLC0415

        cfg = CppQueryInventoryValueConfig()
        cfg.id = id_maps.resource_name_to_id[gv.item]
        cpp_query = _convert_tag_query(gv.query, id_maps, context="QueryInventoryValue")
        cfg.set_query(cpp_query)
        return cfg

    raise ValueError(f"Unknown GameValue type: {type(gv)}")


def _convert_scope(scope: Scope) -> GameValueScope:
    return {
        Scope.AGENT: GameValueScope.AGENT,
        Scope.GAME: GameValueScope.GAME,
        Scope.COLLECTIVE: GameValueScope.COLLECTIVE,
    }[scope]
