"""Convert Python GameValue types to C++ GameValueConfig variants."""

from mettagrid.config.game_value import (
    ConstValue,
    GameValue,
    InventoryValue,
    NumObjectsValue,
    Scope,
    StatValue,
    TagCountValue,
)
from mettagrid.config.tag import typeTag
from mettagrid.mettagrid_c import ConstValueConfig as CppConstValueConfig
from mettagrid.mettagrid_c import GameValueScope
from mettagrid.mettagrid_c import InventoryValueConfig as CppInventoryValueConfig
from mettagrid.mettagrid_c import StatValueConfig as CppStatValueConfig
from mettagrid.mettagrid_c import TagCountValueConfig as CppTagCountValueConfig


def resolve_game_value(gv: GameValue, mappings: dict):
    """Convert a Python GameValue to a C++ typed GameValueConfig variant.

    Args:
        gv: Python GameValue instance
        mappings: Dict with keys:
            - resource_name_to_id: dict[str, int]
            - tag_name_to_id: dict[str, int]

    Returns:
        One of InventoryValueConfig, StatValueConfig, TagCountValueConfig,
        or ConstValueConfig.
    """
    if isinstance(gv, InventoryValue):
        cfg = CppInventoryValueConfig()
        cfg.scope = _convert_scope(gv.scope)
        cfg.id = mappings["resource_name_to_id"][gv.item]
        return cfg

    if isinstance(gv, StatValue):
        cfg = CppStatValueConfig()
        cfg.scope = _convert_scope(gv.scope)
        cfg.stat_name = gv.name
        cfg.delta = gv.delta
        return cfg

    if isinstance(gv, NumObjectsValue):
        cfg = CppTagCountValueConfig()
        tag_name = typeTag(gv.object_type).name
        cfg.id = mappings["tag_name_to_id"][tag_name]
        return cfg

    if isinstance(gv, TagCountValue):
        cfg = CppTagCountValueConfig()
        cfg.id = mappings["tag_name_to_id"][gv.tag]
        return cfg

    if isinstance(gv, ConstValue):
        cfg = CppConstValueConfig()
        cfg.value = gv.value
        return cfg

    raise ValueError(f"Unknown GameValue type: {type(gv)}")


def _convert_scope(scope: Scope) -> GameValueScope:
    return {
        Scope.AGENT: GameValueScope.AGENT,
        Scope.GAME: GameValueScope.GAME,
        Scope.COLLECTIVE: GameValueScope.COLLECTIVE,
    }[scope]
