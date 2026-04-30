"""Discriminated union of all game engine environment configs.

This is a leaf module — it imports every concrete :class:`EnvConfig` subclass
to build the union type.  Nothing should import *from* this module during its
own initialization, so there is no circular-import risk.
"""

from __future__ import annotations

from typing import Annotated, Any, Union

from pydantic import Discriminator
from pydantic import Tag as PydanticTag

from mettagrid.config.bitworld_config import BitWorldEnvConfig
from mettagrid.config.env_config import EnvConfig
from mettagrid.config.mettagrid_config import MettaGridConfig


def _env_config_discriminator(v: Any) -> str:
    """Pick the right union member from a dict or model instance.

    Defaults to ``"mettagrid"`` so legacy dicts that predate the
    ``game_engine`` field still deserialize as :class:`MettaGridConfig`.
    """
    if isinstance(v, dict):
        return v.get("game_engine", "mettagrid")
    return getattr(v, "game_engine", "mettagrid")


AnyEnvConfig = Annotated[
    Union[
        Annotated[MettaGridConfig, PydanticTag("mettagrid")],
        Annotated[BitWorldEnvConfig, PydanticTag("bitworld")],
    ],
    Discriminator(_env_config_discriminator),
]

_ENGINE_TYPE_REGISTRY: dict[str, type[EnvConfig]] = {
    "mettagrid": MettaGridConfig,
    "bitworld": BitWorldEnvConfig,
}


def resolve_env_config_type(config: dict[str, Any]) -> type[EnvConfig]:
    """Return the :class:`EnvConfig` subclass for a raw config dict.

    Uses the ``game_engine`` key (defaulting to ``"mettagrid"`` for legacy
    dicts) to look up the concrete type without fully validating the dict.
    """
    engine = config.get("game_engine", "mettagrid")
    env_type = _ENGINE_TYPE_REGISTRY.get(engine)
    if env_type is None:
        raise ValueError(f"Unknown game engine: {engine!r}")
    return env_type
