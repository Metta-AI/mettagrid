from typing import Optional

import mettagrid.mapgen.scenes.random
from mettagrid.builder import building

# Local import moved to factory usage to avoid forbidden cross-package dependency at import time
from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    AgentConfig,
    AnyGridObjectConfig,
    AttackActionConfig,
    ChangeVibeActionConfig,
    GameConfig,
    InventoryConfig,
    MettaGridConfig,
    MoveActionConfig,
    NoopActionConfig,
    ResourceLimitsConfig,
)
from mettagrid.config.reward_config import inventoryReward
from mettagrid.map_builder.map_builder import MapBuilderConfig
from mettagrid.map_builder.perimeter_incontext import PerimeterInContextMapBuilder
from mettagrid.map_builder.random_map import RandomMapBuilder
from mettagrid.mapgen.mapgen import MapGen


def make_arena(
    num_agents: int,
    combat: bool = True,
    map_builder: MapBuilderConfig | None = None,  # custom map builder; must match num_agents
) -> MettaGridConfig:
    objects: dict[str, AnyGridObjectConfig] = {
        "wall": building.wall,
    }

    actions = ActionsConfig(
        noop=NoopActionConfig(),
        move=MoveActionConfig(),
        attack=AttackActionConfig(
            consumed_resources={
                "laser": 1,
            },
            defense_resources={
                "armor": 1,
            },
        ),
        change_vibe=ChangeVibeActionConfig(enabled=False),
    )

    if not combat:
        actions.attack.consumed_resources = {"laser": 100}

    if map_builder is None:
        map_builder = MapGen.Config(
            num_agents=num_agents,
            width=25,
            height=25,
            border_width=6,
            instance_border_width=0,
            instance=mettagrid.mapgen.scenes.random.Random.Config(
                agents=6,
                objects={
                    "wall": 10,
                },
            ),
        )

    return MettaGridConfig(
        label="arena" + (".combat" if combat else ""),
        game=GameConfig(
            num_agents=num_agents,
            actions=actions,
            objects=objects,
            agent=AgentConfig(
                inventory=InventoryConfig(
                    default_limit=50,
                    limits={
                        "heart": ResourceLimitsConfig(min=255, resources=["heart"]),
                    },
                ),
                rewards={"heart": inventoryReward("heart")},
            ),
            map_builder=map_builder,
        ),
    )


def make_navigation(num_agents: int) -> MettaGridConfig:
    cfg = MettaGridConfig(
        game=GameConfig(
            num_agents=num_agents,
            objects={
                "wall": building.wall,
            },
            resource_names=["heart"],
            actions=ActionsConfig(
                move=MoveActionConfig(enabled=True),
                noop=NoopActionConfig(enabled=True),
            ),
            agent=AgentConfig(
                rewards={"heart": inventoryReward("heart")},
            ),
            # Always provide a concrete map builder config so tests can set width/height
            map_builder=RandomMapBuilder.Config(agents=num_agents),
        )
    )
    return cfg


def make_assembly_lines(
    num_agents: int,
    max_steps,
    game_objects: dict,
    map_builder_objects: dict,
    width: int = 6,
    height: int = 6,
    terrain: str = "no-terrain",
    chain_length: int = 2,
    num_sinks: int = 0,
    dir: Optional[str] = None,
) -> MettaGridConfig:
    game_objects["wall"] = building.wall
    cfg = MettaGridConfig(
        desync_episodes=False,
        game=GameConfig(
            max_steps=max_steps,
            num_agents=num_agents,
            objects=game_objects,
            map_builder=MapGen.Config(
                instances=num_agents,
                instance=PerimeterInContextMapBuilder.Config(
                    agents=1,
                    width=width,
                    height=height,
                    objects=map_builder_objects,
                    density=terrain,
                    chain_length=chain_length,
                    num_sinks=num_sinks,
                    dir=dir,
                ),
            ),
            actions=ActionsConfig(
                noop=NoopActionConfig(),
                move=MoveActionConfig(),
            ),
            agent=AgentConfig(
                rewards={"heart": inventoryReward("heart")},
                inventory=InventoryConfig(
                    default_limit=1,
                    limits={"heart": ResourceLimitsConfig(min=15, resources=["heart"])},
                ),
            ),
        ),
    )
    return cfg
