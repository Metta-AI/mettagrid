"""Convert Python GameValue types to C++ GameValueConfig."""

from mettagrid.config.game_value import (
    GameValue,
    InventoryValue,
    NumObjectsValue,
    Scope,
    StatValue,
    TagCountValue,
)
from mettagrid.config.tag import typeTag
from mettagrid.mettagrid_c import GameValueConfig as CppGameValueConfig
from mettagrid.mettagrid_c import GameValueScope, GameValueType


def resolve_game_value(gv: GameValue, mappings: dict) -> CppGameValueConfig:
    """Convert a Python GameValue to a C++ GameValueConfig.

    Args:
        gv: Python GameValue instance
        mappings: Dict with keys:
            - resource_name_to_id: dict[str, int]
            - tag_name_to_id: dict[str, int]

    Returns:
        CppGameValueConfig with resolved type, scope, id, stat_name, and delta.
    """
    cfg = CppGameValueConfig()

    if isinstance(gv, InventoryValue):
        cfg.type = GameValueType.INVENTORY
        cfg.scope = _convert_scope(gv.scope)
        cfg.id = mappings["resource_name_to_id"][gv.item]
    elif isinstance(gv, StatValue):
        cfg.type = GameValueType.STAT
        cfg.scope = _convert_scope(gv.scope)
        cfg.stat_name = gv.name
        cfg.delta = gv.delta
    elif isinstance(gv, NumObjectsValue):
        cfg.type = GameValueType.TAG_COUNT
        cfg.scope = GameValueScope.GAME
        tag_name = str(typeTag(gv.object_type))
        cfg.id = mappings["tag_name_to_id"][tag_name]
    elif isinstance(gv, TagCountValue):
        cfg.type = GameValueType.TAG_COUNT
        cfg.scope = GameValueScope.GAME
        cfg.id = mappings["tag_name_to_id"][gv.tag]
    else:
        raise ValueError(f"Unknown GameValue type: {type(gv)}")

    return cfg


def _convert_scope(scope: Scope) -> GameValueScope:
    return {
        Scope.AGENT: GameValueScope.AGENT,
        Scope.COLLECTIVE: GameValueScope.COLLECTIVE,
        Scope.GAME: GameValueScope.GAME,
    }[scope]
