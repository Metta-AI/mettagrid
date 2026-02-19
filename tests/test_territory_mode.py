from mettagrid.config.filter import AlignmentFilter
from mettagrid.config.handler_config import (
    AlignmentCondition,
    AOEConfig,
    HandlerTarget,
)
from mettagrid.config.mettagrid_config import (
    CollectiveConfig,
    GridObjectConfig,
    InventoryConfig,
    MettaGridConfig,
)
from mettagrid.config.mutation import updateTarget
from mettagrid.simulator import Simulation
from mettagrid.simulator.interface import Location
from mettagrid.test_support.observation_helper import ObservationHelper


def test_territory_map_observation_tokens_emitted_for_empty_cells() -> None:
    cfg = MettaGridConfig.EmptyRoom(num_agents=1, width=5, height=5, border_width=0).with_ascii_map(
        [
            ".....",
            "..E..",
            "..@..",
            "..F..",
            ".....",
        ],
        char_to_map_name={"E": "enemy_source", "F": "friendly_source"},
    )
    cfg.game.obs.width = 5
    cfg.game.obs.height = 5
    cfg.game.obs.num_tokens = 200
    cfg.game.obs.aoe_mask = True
    cfg.game.resource_names = []
    cfg.game.agent.collective = "cogs"
    cfg.game.collectives = {
        "cogs": CollectiveConfig(inventory=InventoryConfig()),
        "clips": CollectiveConfig(inventory=InventoryConfig()),
    }
    cfg.game.objects["friendly_source"] = GridObjectConfig(
        name="friendly_source",
        map_name="friendly_source",
        collective="cogs",
        aoes={
            "friendly": AOEConfig(
                radius=2,
                controls_territory=True,
                filters=[
                    AlignmentFilter(target=HandlerTarget.TARGET, alignment=AlignmentCondition.SAME_COLLECTIVE),
                ],
            )
        },
    )
    cfg.game.objects["enemy_source"] = GridObjectConfig(
        name="enemy_source",
        map_name="enemy_source",
        collective="clips",
        aoes={
            "enemy": AOEConfig(
                radius=2,
                controls_territory=True,
                filters=[
                    AlignmentFilter(target=HandlerTarget.TARGET, alignment=AlignmentCondition.DIFFERENT_COLLECTIVE),
                ],
            )
        },
    )

    sim = Simulation(cfg)
    obs = sim._c_sim.observations()[0]
    territory_feature_id = sim.config.game.id_map().feature_id("aoe_mask")

    def territory_at(row: int, col: int) -> int | None:
        vals = ObservationHelper.find_token_values(
            obs, location=Location(row, col), feature_id=territory_feature_id, is_global=False
        )
        if len(vals) == 0:
            return None
        assert len(vals) == 1
        return int(vals[0])

    # Center cell is in range of both territory AOEs: contested => neutral => no token.
    assert territory_at(2, 2) is None

    # Fight: when both cover a tile, the closer side wins (midpoint ties are neutral).
    # (3,3) is in range of both sources but closer to the friendly source at (3,2).
    assert territory_at(3, 3) == 1

    # (4,4) is outside Euclidean radius 2 from (3,2): no token.
    assert territory_at(4, 4) is None

    # (4,3) is only in range of the friendly source.
    assert territory_at(4, 3) == 1

    # (0,0) is outside Euclidean radius 2 from (1,2): no token.
    assert territory_at(0, 0) is None

    # (0,1) is only in range of the enemy source.
    assert territory_at(0, 1) == 2


def test_mutating_aoes_stack_overlapping_sources() -> None:
    def make_cfg(map_data: list[str]) -> MettaGridConfig:
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, width=5, height=5, with_walls=True).with_ascii_map(
            map_data,
            char_to_map_name={"E": "enemy_source", "F": "friendly_source"},
        )
        cfg.game.resource_names = ["hp"]
        cfg.game.agent.collective = "cogs"
        cfg.game.agent.inventory.initial = {"hp": 10}
        cfg.game.collectives = {
            "cogs": CollectiveConfig(inventory=InventoryConfig()),
            "clips": CollectiveConfig(inventory=InventoryConfig()),
        }
        cfg.game.objects["enemy_source"] = GridObjectConfig(
            name="enemy_source",
            map_name="enemy_source",
            collective="clips",
            aoes={
                "enemy": AOEConfig(
                    radius=3,
                    filters=[
                        AlignmentFilter(
                            target=HandlerTarget.TARGET,
                            alignment=AlignmentCondition.DIFFERENT_COLLECTIVE,
                        )
                    ],
                    mutations=[updateTarget({"hp": -1})],
                )
            },
        )
        return cfg

    sim = Simulation(make_cfg(["#####", "#.E.#", "#.@.#", "#.E.#", "#####"]))
    sim.agent(0).set_action("noop")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == 8

    contested = make_cfg([".....", "..E..", "..@..", "..F..", "....."])
    contested.game.objects["friendly_source"] = GridObjectConfig(
        name="friendly_source",
        map_name="friendly_source",
        collective="cogs",
        aoes={
            "friendly": AOEConfig(
                radius=3,
                filters=[
                    AlignmentFilter(
                        target=HandlerTarget.TARGET,
                        alignment=AlignmentCondition.SAME_COLLECTIVE,
                    )
                ],
                mutations=[updateTarget({"hp": +100})],
            )
        },
    )

    sim2 = Simulation(contested)
    sim2.agent(0).set_action("noop")
    sim2.step()
    assert sim2.agent(0).inventory.get("hp", 0) == 109


def test_mutating_aoes_do_not_emit_territory_ownership_tokens() -> None:
    cfg = MettaGridConfig.EmptyRoom(num_agents=1, width=5, height=5, border_width=0).with_ascii_map(
        [
            ".....",
            "..E..",
            "..@..",
            ".....",
            ".....",
        ],
        char_to_map_name={"E": "enemy_source"},
    )
    cfg.game.obs.width = 5
    cfg.game.obs.height = 5
    cfg.game.obs.num_tokens = 200
    cfg.game.obs.aoe_mask = True
    cfg.game.resource_names = ["hp"]
    cfg.game.agent.collective = "cogs"
    cfg.game.agent.inventory.initial = {"hp": 10}
    cfg.game.collectives = {
        "cogs": CollectiveConfig(inventory=InventoryConfig()),
        "clips": CollectiveConfig(inventory=InventoryConfig()),
    }
    cfg.game.objects["enemy_source"] = GridObjectConfig(
        name="enemy_source",
        map_name="enemy_source",
        collective="clips",
        aoes={
            "enemy": AOEConfig(
                radius=2,
                filters=[
                    AlignmentFilter(
                        target=HandlerTarget.TARGET,
                        alignment=AlignmentCondition.DIFFERENT_COLLECTIVE,
                    )
                ],
                mutations=[updateTarget({"hp": -1})],
            )
        },
    )

    sim = Simulation(cfg)
    obs = sim._c_sim.observations()[0]
    territory_feature_id = sim.config.game.id_map().feature_id("aoe_mask")

    vals = ObservationHelper.find_token_values(
        obs, location=Location(2, 2), feature_id=territory_feature_id, is_global=False
    )
    assert len(vals) == 0

    sim.agent(0).set_action("noop")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == 9


def test_territory_controlled_mutating_aoes_use_winning_side_and_preserve_stacking() -> None:
    cfg = MettaGridConfig.EmptyRoom(num_agents=1, width=5, height=5, border_width=0).with_ascii_map(
        [
            ".....",
            "..E..",
            "F.@..",
            "..E..",
            ".....",
        ],
        char_to_map_name={"E": "enemy_source", "F": "friendly_source"},
    )
    cfg.game.obs.width = 5
    cfg.game.obs.height = 5
    cfg.game.obs.num_tokens = 200
    cfg.game.obs.aoe_mask = True
    cfg.game.resource_names = ["hp"]
    cfg.game.agent.collective = "cogs"
    cfg.game.agent.inventory.initial = {"hp": 10}
    cfg.game.collectives = {
        "cogs": CollectiveConfig(inventory=InventoryConfig()),
        "clips": CollectiveConfig(inventory=InventoryConfig()),
    }
    cfg.game.objects["enemy_source"] = GridObjectConfig(
        name="enemy_source",
        map_name="enemy_source",
        collective="clips",
        aoes={
            "enemy": AOEConfig(
                radius=3,
                controls_territory=True,
                filters=[
                    AlignmentFilter(
                        target=HandlerTarget.TARGET,
                        alignment=AlignmentCondition.DIFFERENT_COLLECTIVE,
                    )
                ],
                mutations=[updateTarget({"hp": -1})],
            )
        },
    )
    cfg.game.objects["friendly_source"] = GridObjectConfig(
        name="friendly_source",
        map_name="friendly_source",
        collective="cogs",
        aoes={
            "friendly": AOEConfig(
                radius=3,
                controls_territory=True,
                filters=[
                    AlignmentFilter(
                        target=HandlerTarget.TARGET,
                        alignment=AlignmentCondition.SAME_COLLECTIVE,
                    )
                ],
                mutations=[updateTarget({"hp": +100})],
            )
        },
    )

    sim = Simulation(cfg)
    obs = sim._c_sim.observations()[0]
    territory_feature_id = sim.config.game.id_map().feature_id("aoe_mask")

    vals = ObservationHelper.find_token_values(
        obs, location=Location(2, 2), feature_id=territory_feature_id, is_global=False
    )
    assert len(vals) == 1
    assert int(vals[0]) == 2

    sim.agent(0).set_action("noop")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == 8
