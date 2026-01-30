# Rebuild models that depend on forward-referenced filter/mutation types.
# Many modules use `from __future__ import annotations`, making all annotations lazy
# strings. Pydantic needs all referenced types in scope when resolving them.
# We collect the full namespaces from filter and mutation packages.
import mettagrid.config.filter as _filter_pkg
import mettagrid.config.mutation as _mutation_pkg
from mettagrid.config.event_config import EventConfig as _EventConfig
from mettagrid.config.handler_config import AOEConfig, Handler

from .action_config import (
    ActionConfig,
    ActionsConfig,
    AttackActionConfig,
    AttackOutcome,
    CardinalDirection,
    CardinalDirections,
    ChangeVibeActionConfig,
    Direction,
    Directions,
    MoveActionConfig,
    NoopActionConfig,
    TransferActionConfig,
    VibeTransfer,
)
from .game_value import (
    AnyGameValue,
    GameValue,
    InventoryValue,
    NumObjectsValue,
    Scope,
    StatValue,
    TagCountValue,
)
from .mettagrid_c_config import convert_to_cpp_game_config
from .mettagrid_config import (
    AgentConfig,
    GameConfig,
    MettaGridConfig,
    ProtocolConfig,
    WallConfig,
)
from .obs_config import GlobalObsConfig
from .reward_config import (
    AgentReward,
    collectiveInventoryReward,
    inventoryReward,
    numObjectsReward,
    numTaggedReward,
    reward,
    stat,
    statReward,
)

_rebuild_ns: dict = {}
_rebuild_ns.update({k: v for k, v in vars(_filter_pkg).items() if not k.startswith("_")})
_rebuild_ns.update({k: v for k, v in vars(_mutation_pkg).items() if not k.startswith("_")})

Handler.model_rebuild(_types_namespace=_rebuild_ns)
AOEConfig.model_rebuild(_types_namespace=_rebuild_ns)
_EventConfig.model_rebuild(_types_namespace=_rebuild_ns)
WallConfig.model_rebuild(_types_namespace=_rebuild_ns)
AgentConfig.model_rebuild(_types_namespace=_rebuild_ns)
GameConfig.model_rebuild(_types_namespace=_rebuild_ns)
MettaGridConfig.model_rebuild(_types_namespace=_rebuild_ns)

__all__ = [
    "ActionConfig",
    "ActionsConfig",
    "AgentConfig",
    "AgentReward",
    "AnyGameValue",
    "AttackActionConfig",
    "AttackOutcome",
    "CardinalDirection",
    "CardinalDirections",
    "ChangeVibeActionConfig",
    "collectiveInventoryReward",
    "convert_to_cpp_game_config",
    "Direction",
    "Directions",
    "GameConfig",
    "GameValue",
    "GlobalObsConfig",
    "InventoryValue",
    "inventoryReward",
    "MettaGridConfig",
    "MoveActionConfig",
    "NoopActionConfig",
    "NumObjectsValue",
    "numObjectsReward",
    "numTaggedReward",
    "ProtocolConfig",
    "reward",
    "Scope",
    "stat",
    "StatValue",
    "statReward",
    "TagCountValue",
    "TransferActionConfig",
    "VibeTransfer",
    "WallConfig",
]
