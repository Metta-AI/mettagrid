"""Game registration and lookup for CoGames."""

from __future__ import annotations

from typing import Sequence

from mettagrid.cogame.core import CoGameMission, CoGameMissionVariant
from mettagrid.cogame.variants import VariantRegistry


class CoGame:
    """Base class for CoGames. Holds missions and a variant registry."""

    name: str
    missions: list[CoGameMission]
    variant_registry: VariantRegistry
    eval_missions: list[CoGameMission]

    def __init__(
        self,
        name: str,
        missions: Sequence[CoGameMission],
        variants: Sequence[CoGameMissionVariant],
        eval_missions: Sequence[CoGameMission] | None = None,
    ) -> None:
        self.name = name
        self.missions = list(missions)
        self.variant_registry = VariantRegistry(list(variants))
        self.eval_missions = list(eval_missions) if eval_missions else []


_GAMES: dict[str, "CoGame"] = {}


def get_game(name: str) -> "CoGame":
    """Get a registered game by name.

    The game module must be imported (which calls register_game) before lookup.
    Raises ValueError if the game is not registered.
    """
    if name not in _GAMES:
        raise ValueError(f"Unknown game '{name}'. Registered: {', '.join(sorted(_GAMES))}")
    return _GAMES[name]


def register_game(game: "CoGame") -> None:
    """Register a game for lookup by name."""
    _GAMES[game.name] = game
