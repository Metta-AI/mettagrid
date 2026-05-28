"""CoGame mission and variant framework.

Public surface for downstream games (e.g. cogame-tag, cogame-memory,
cogame-cogsguard) to define MettaGrid missions and composable variants.
"""

from mettagrid.cogame.core import (
    CoGameMission,
    CoGameMissionVariant,
    CvCStationConfig,
    Deps,
)
from mettagrid.cogame.game import CoGame, get_game, register_game
from mettagrid.cogame.variants import ResolvedDeps, VariantRegistry

__all__ = [
    "CoGame",
    "CoGameMission",
    "CoGameMissionVariant",
    "CvCStationConfig",
    "Deps",
    "ResolvedDeps",
    "VariantRegistry",
    "get_game",
    "register_game",
]
