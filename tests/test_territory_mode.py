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
    cfg.game.obs.territory = True
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
                filters=[
                    AlignmentFilter(target=HandlerTarget.TARGET, alignment=AlignmentCondition.DIFFERENT_COLLECTIVE),
                ],
            )
        },
    )

    sim = Simulation(cfg)
    obs = sim._c_sim.observations()[0]
    territory_feature_id = sim.config.game.id_map().feature_id("territory")

    def territory_at(row: int, col: int) -> int | None:
        vals = ObservationHelper.find_token_values(
            obs, location=Location(row, col), feature_id=territory_feature_id, is_global=False
        )
        if len(vals) == 0:
            return None
        assert len(vals) == 1
        return int(vals[0])

    # Center cell is a midpoint tie between cogs and clips. Clips loses ties.
    assert territory_at(2, 2) == 1

    # Fight: when both cover a tile, the closer side wins.
    # (3,3) is in range of both sources but closer to the friendly source at (3,2).
    assert territory_at(3, 3) == 1

    # (4,4) is outside Euclidean radius 2 from (3,2): no token.
    assert territory_at(4, 4) is None

    # (4,2) is only in range of the friendly source and inside circular local vision.
    assert territory_at(4, 2) == 1

    # (0,0) is outside Euclidean radius 2 from (1,2): no token.
    assert territory_at(0, 0) is None

    # (0,2) is only in range of the enemy source and inside circular local vision.
    assert territory_at(0, 2) == 2


def test_territory_midpoint_tie_without_clips_stays_neutral() -> None:
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
    cfg.game.obs.territory = True
    cfg.game.resource_names = []
    cfg.game.agent.collective = "alpha"
    cfg.game.collectives = {
        "alpha": CollectiveConfig(inventory=InventoryConfig()),
        "beta": CollectiveConfig(inventory=InventoryConfig()),
    }
    cfg.game.objects["friendly_source"] = GridObjectConfig(
        name="friendly_source",
        map_name="friendly_source",
        collective="alpha",
        aoes={
            "friendly": AOEConfig(
                radius=2,
                filters=[
                    AlignmentFilter(target=HandlerTarget.TARGET, alignment=AlignmentCondition.SAME_COLLECTIVE),
                ],
            )
        },
    )
    cfg.game.objects["enemy_source"] = GridObjectConfig(
        name="enemy_source",
        map_name="enemy_source",
        collective="beta",
        aoes={
            "enemy": AOEConfig(
                radius=2,
                filters=[
                    AlignmentFilter(target=HandlerTarget.TARGET, alignment=AlignmentCondition.DIFFERENT_COLLECTIVE),
                ],
            )
        },
    )

    sim = Simulation(cfg)
    obs = sim._c_sim.observations()[0]
    territory_feature_id = sim.config.game.id_map().feature_id("territory")
    vals = ObservationHelper.find_token_values(
        obs, location=Location(2, 2), feature_id=territory_feature_id, is_global=False
    )
    assert len(vals) == 0


def test_territory_excludes_exact_cardinal_radius_boundary_points() -> None:
    cfg = MettaGridConfig.EmptyRoom(num_agents=1, width=7, height=7, border_width=0).with_ascii_map(
        [
            ".......",
            ".......",
            ".......",
            "...@F..",
            ".......",
            ".......",
            ".......",
        ],
        char_to_map_name={"F": "friendly_source"},
    )
    cfg.game.obs.width = 7
    cfg.game.obs.height = 7
    cfg.game.obs.num_tokens = 300
    cfg.game.obs.territory = True
    cfg.game.resource_names = []
    cfg.game.agent.collective = "cogs"
    cfg.game.collectives = {"cogs": CollectiveConfig(inventory=InventoryConfig())}
    cfg.game.objects["friendly_source"] = GridObjectConfig(
        name="friendly_source",
        map_name="friendly_source",
        collective="cogs",
        aoes={
            "friendly": AOEConfig(
                radius=2,
                filters=[
                    AlignmentFilter(target=HandlerTarget.TARGET, alignment=AlignmentCondition.SAME_COLLECTIVE),
                ],
            )
        },
    )

    sim = Simulation(cfg)
    obs = sim._c_sim.observations()[0]
    territory_feature_id = sim.config.game.id_map().feature_id("territory")

    def territory_at(row: int, col: int) -> int | None:
        vals = ObservationHelper.find_token_values(
            obs, location=Location(row, col), feature_id=territory_feature_id, is_global=False
        )
        if len(vals) == 0:
            return None
        assert len(vals) == 1
        return int(vals[0])

    # Radius-2 cardinal boundary points are excluded from territory ownership.
    assert territory_at(1, 4) is None
    assert territory_at(3, 2) is None
    assert territory_at(3, 6) is None
    assert territory_at(5, 4) is None
    # Nearby non-cardinal points remain controlled.
    assert territory_at(2, 3) == 1
    assert territory_at(4, 5) == 1


def test_territory_midpoint_tie_against_clips_favors_non_clips() -> None:
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
    cfg.game.obs.territory = True
    cfg.game.resource_names = []
    cfg.game.agent.collective = "alpha"
    cfg.game.collectives = {
        "alpha": CollectiveConfig(inventory=InventoryConfig()),
        "clips": CollectiveConfig(inventory=InventoryConfig()),
    }
    cfg.game.objects["friendly_source"] = GridObjectConfig(
        name="friendly_source",
        map_name="friendly_source",
        collective="alpha",
        aoes={
            "friendly": AOEConfig(
                radius=2,
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
                filters=[
                    AlignmentFilter(target=HandlerTarget.TARGET, alignment=AlignmentCondition.DIFFERENT_COLLECTIVE),
                ],
            )
        },
    )

    sim = Simulation(cfg)
    obs = sim._c_sim.observations()[0]
    territory_feature_id = sim.config.game.id_map().feature_id("territory")
    vals = ObservationHelper.find_token_values(
        obs, location=Location(2, 2), feature_id=territory_feature_id, is_global=False
    )
    assert len(vals) == 1
    assert int(vals[0]) == 1


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
    cfg.game.obs.territory = True
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
    territory_feature_id = sim.config.game.id_map().feature_id("territory")

    vals = ObservationHelper.find_token_values(
        obs, location=Location(2, 2), feature_id=territory_feature_id, is_global=False
    )
    assert len(vals) == 0

    sim.agent(0).set_action("noop")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == 9


def test_territory_ownership_comes_from_non_mutating_aoes() -> None:
    cfg = MettaGridConfig.EmptyRoom(num_agents=1, width=5, height=5, border_width=0).with_ascii_map(
        [
            ".....",
            "..E..",
            "F.@..",
            ".....",
            ".....",
        ],
        char_to_map_name={"E": "enemy_station", "F": "friendly_station"},
    )
    cfg.game.obs.width = 5
    cfg.game.obs.height = 5
    cfg.game.obs.num_tokens = 200
    cfg.game.obs.territory = True
    cfg.game.resource_names = ["hp"]
    cfg.game.agent.collective = "cogs"
    cfg.game.agent.inventory.initial = {"hp": 10}
    cfg.game.collectives = {
        "cogs": CollectiveConfig(inventory=InventoryConfig()),
        "clips": CollectiveConfig(inventory=InventoryConfig()),
    }
    cfg.game.objects["enemy_station"] = GridObjectConfig(
        name="enemy_station",
        map_name="enemy_station",
        collective="clips",
        aoes={
            "territory": AOEConfig(
                radius=3,
                filters=[
                    AlignmentFilter(
                        target=HandlerTarget.TARGET,
                        alignment=AlignmentCondition.DIFFERENT_COLLECTIVE,
                    )
                ],
            ),
            "enemy_effect": AOEConfig(
                radius=3,
                filters=[
                    AlignmentFilter(
                        target=HandlerTarget.TARGET,
                        alignment=AlignmentCondition.DIFFERENT_COLLECTIVE,
                    )
                ],
                mutations=[updateTarget({"hp": -1})],
            ),
        },
    )
    cfg.game.objects["friendly_station"] = GridObjectConfig(
        name="friendly_station",
        map_name="friendly_station",
        collective="cogs",
        aoes={
            "territory": AOEConfig(
                radius=3,
                filters=[
                    AlignmentFilter(
                        target=HandlerTarget.TARGET,
                        alignment=AlignmentCondition.SAME_COLLECTIVE,
                    )
                ],
            ),
            "friendly_effect": AOEConfig(
                radius=3,
                filters=[
                    AlignmentFilter(
                        target=HandlerTarget.TARGET,
                        alignment=AlignmentCondition.SAME_COLLECTIVE,
                    )
                ],
                mutations=[updateTarget({"hp": +100})],
            ),
        },
    )

    sim = Simulation(cfg)
    obs = sim._c_sim.observations()[0]
    territory_feature_id = sim.config.game.id_map().feature_id("territory")

    vals = ObservationHelper.find_token_values(
        obs, location=Location(2, 2), feature_id=territory_feature_id, is_global=False
    )
    assert len(vals) == 1
    assert int(vals[0]) == 2

    sim.agent(0).set_action("noop")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == 109
