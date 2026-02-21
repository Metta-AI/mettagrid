import pytest

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


def _weighted_territory_aoe(
    *,
    radius: int,
    alignment: AlignmentCondition,
) -> AOEConfig:
    return AOEConfig(
        radius=radius,
        filters=[AlignmentFilter(target=HandlerTarget.TARGET, alignment=alignment)],
    )


def _collective_map(*collectives: str) -> dict[str, CollectiveConfig]:
    return {name: CollectiveConfig(inventory=InventoryConfig()) for name in collectives}


def _make_territory_cfg(
    *,
    map_data: list[str],
    char_to_map_name: dict[str, str],
    agent_collective: str,
    collectives: tuple[str, ...],
    num_tokens: int,
) -> MettaGridConfig:
    cfg = MettaGridConfig.EmptyRoom(
        num_agents=1,
        width=len(map_data[0]),
        height=len(map_data),
        border_width=0,
    ).with_ascii_map(map_data, char_to_map_name=char_to_map_name)
    cfg.game.obs.width = len(map_data[0])
    cfg.game.obs.height = len(map_data)
    cfg.game.obs.num_tokens = num_tokens
    cfg.game.obs.aoe_mask = True
    cfg.game.resource_names = []
    cfg.game.agent.collective = agent_collective
    cfg.game.collectives = _collective_map(*collectives)
    return cfg


def _territory_object(
    *,
    name: str,
    map_name: str,
    collective: str,
    radius: int,
    alignment: AlignmentCondition,
    aoe_name: str = "territory",
) -> GridObjectConfig:
    territory_aoe = _weighted_territory_aoe(
        radius=radius,
        alignment=alignment,
    )

    return GridObjectConfig(
        name=name,
        map_name=map_name,
        collective=collective,
        aoes={aoe_name: territory_aoe},
    )


def _territory_lookup(cfg: MettaGridConfig):
    sim = Simulation(cfg)
    obs = sim._c_sim.observations()[0]
    aoe_mask_feature_id = sim.config.game.id_map().feature_id("aoe_mask")

    def territory_at(row: int, col: int) -> int | None:
        vals = ObservationHelper.find_token_values(
            obs, location=Location(row, col), feature_id=aoe_mask_feature_id, is_global=False
        )
        if len(vals) == 0:
            return None
        assert len(vals) == 1
        return int(vals[0])

    return territory_at


@pytest.mark.parametrize("enemy_collective", ["beta", "clips"])
def test_territory_midpoint_tie_stays_neutral(enemy_collective: str) -> None:
    cfg = _make_territory_cfg(
        map_data=[
            ".....",
            "..E..",
            "..@..",
            "..F..",
            ".....",
        ],
        char_to_map_name={"E": "enemy_source", "F": "friendly_source"},
        agent_collective="alpha",
        collectives=("alpha", enemy_collective),
        num_tokens=200,
    )
    cfg.game.objects["friendly_source"] = _territory_object(
        name="friendly_source",
        map_name="friendly_source",
        collective="alpha",
        radius=2,
        alignment=AlignmentCondition.SAME_COLLECTIVE,
        aoe_name="friendly",
    )
    cfg.game.objects["enemy_source"] = _territory_object(
        name="enemy_source",
        map_name="enemy_source",
        collective=enemy_collective,
        radius=2,
        alignment=AlignmentCondition.DIFFERENT_COLLECTIVE,
        aoe_name="enemy",
    )

    territory_at = _territory_lookup(cfg)
    assert territory_at(2, 2) is None


def test_territory_excludes_exact_cardinal_radius_boundary_points() -> None:
    cfg = _make_territory_cfg(
        map_data=[
            ".......",
            ".......",
            ".......",
            "...@F..",
            ".......",
            ".......",
            ".......",
        ],
        char_to_map_name={"F": "friendly_source"},
        agent_collective="cogs",
        collectives=("cogs",),
        num_tokens=300,
    )
    cfg.game.objects["friendly_source"] = _territory_object(
        name="friendly_source",
        map_name="friendly_source",
        collective="cogs",
        radius=2,
        alignment=AlignmentCondition.SAME_COLLECTIVE,
        aoe_name="friendly",
    )

    territory_at = _territory_lookup(cfg)
    assert territory_at(1, 4) is None
    assert territory_at(3, 2) is None
    assert territory_at(3, 6) is None
    assert territory_at(5, 4) is None
    assert territory_at(2, 3) == 1
    assert territory_at(4, 5) == 1


@pytest.mark.parametrize(
    ("radius", "expected_owned", "expected_neutral"),
    [
        (0, [], [(2, 2), (2, 3)]),
        (1, [(2, 3)], [(2, 2)]),
    ],
)
def test_small_radius_territory_coverage(
    radius: int,
    expected_owned: list[tuple[int, int]],
    expected_neutral: list[tuple[int, int]],
) -> None:
    cfg = _make_territory_cfg(
        map_data=[
            ".....",
            ".....",
            "..@F.",
            ".....",
            ".....",
        ],
        char_to_map_name={"F": "friendly_source"},
        agent_collective="cogs",
        collectives=("cogs",),
        num_tokens=200,
    )
    cfg.game.objects["friendly_source"] = _territory_object(
        name="friendly_source",
        map_name="friendly_source",
        collective="cogs",
        radius=radius,
        alignment=AlignmentCondition.SAME_COLLECTIVE,
        aoe_name="friendly",
    )

    territory_at = _territory_lookup(cfg)
    for row, col in expected_owned:
        assert territory_at(row, col) == 1
    for row, col in expected_neutral:
        assert territory_at(row, col) is None


def test_weighted_territory_influence_allows_multiple_sources_to_outcompete_one() -> None:
    cfg = _make_territory_cfg(
        map_data=[
            ".......",
            "...E...",
            ".......",
            "...@.F.",
            ".......",
            "...E...",
            ".......",
        ],
        char_to_map_name={"E": "enemy_source", "F": "friendly_source"},
        agent_collective="cogs",
        collectives=("cogs", "clips"),
        num_tokens=300,
    )
    cfg.game.objects["friendly_source"] = _territory_object(
        name="friendly_source",
        map_name="friendly_source",
        collective="cogs",
        radius=3,
        alignment=AlignmentCondition.SAME_COLLECTIVE,
    )
    cfg.game.objects["enemy_source"] = _territory_object(
        name="enemy_source",
        map_name="enemy_source",
        collective="clips",
        radius=3,
        alignment=AlignmentCondition.DIFFERENT_COLLECTIVE,
    )

    territory_at = _territory_lookup(cfg)
    assert territory_at(3, 3) == 2


def test_weighted_territory_influence_reaches_zero_on_radius_boundary() -> None:
    cfg = _make_territory_cfg(
        map_data=[
            ".......",
            ".......",
            ".......",
            "...@F..",
            ".......",
            ".......",
            ".......",
        ],
        char_to_map_name={"F": "friendly_source"},
        agent_collective="cogs",
        collectives=("cogs",),
        num_tokens=300,
    )
    cfg.game.objects["friendly_source"] = _territory_object(
        name="friendly_source",
        map_name="friendly_source",
        collective="cogs",
        radius=3,
        alignment=AlignmentCondition.SAME_COLLECTIVE,
    )

    territory_at = _territory_lookup(cfg)
    assert territory_at(0, 4) is None


@pytest.mark.parametrize(
    ("friendly_radius", "expected_territory"),
    [
        (5, 1),
        (2, 2),
    ],
)
def test_weighted_territory_with_different_radii(
    friendly_radius: int,
    expected_territory: int | None,
) -> None:
    cfg = _make_territory_cfg(
        map_data=[
            ".......",
            ".......",
            ".......",
            "..E@.F.",
            ".......",
            ".......",
            ".......",
        ],
        char_to_map_name={"E": "enemy_source", "F": "friendly_source"},
        agent_collective="cogs",
        collectives=("cogs", "clips"),
        num_tokens=300,
    )
    cfg.game.objects["friendly_source"] = _territory_object(
        name="friendly_source",
        map_name="friendly_source",
        collective="cogs",
        radius=friendly_radius,
        alignment=AlignmentCondition.SAME_COLLECTIVE,
    )
    cfg.game.objects["enemy_source"] = _territory_object(
        name="enemy_source",
        map_name="enemy_source",
        collective="clips",
        radius=3,
        alignment=AlignmentCondition.DIFFERENT_COLLECTIVE,
    )

    territory_at = _territory_lookup(cfg)
    assert territory_at(3, 3) == expected_territory


def test_mutating_aoes_stack_overlapping_sources() -> None:
    def make_cfg(map_data: list[str]) -> MettaGridConfig:
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, width=5, height=5, with_walls=True).with_ascii_map(
            map_data,
            char_to_map_name={"E": "enemy_source", "F": "friendly_source"},
        )
        cfg.game.resource_names = ["hp"]
        cfg.game.agent.collective = "cogs"
        cfg.game.agent.inventory.initial = {"hp": 10}
        cfg.game.collectives = _collective_map("cogs", "clips")
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
    cfg = _make_territory_cfg(
        map_data=[
            ".....",
            "..E..",
            "..@..",
            ".....",
            ".....",
        ],
        char_to_map_name={"E": "enemy_source"},
        agent_collective="cogs",
        collectives=("cogs", "clips"),
        num_tokens=200,
    )
    cfg.game.resource_names = ["hp"]
    cfg.game.agent.inventory.initial = {"hp": 10}
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

    territory_at = _territory_lookup(cfg)
    assert territory_at(2, 2) is None

    sim = Simulation(cfg)
    sim.agent(0).set_action("noop")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == 9


def test_territory_ownership_comes_from_non_mutating_aoes() -> None:
    cfg = _make_territory_cfg(
        map_data=[
            ".....",
            "..E..",
            "F.@..",
            ".....",
            ".....",
        ],
        char_to_map_name={"E": "enemy_station", "F": "friendly_station"},
        agent_collective="cogs",
        collectives=("cogs", "clips"),
        num_tokens=200,
    )
    cfg.game.resource_names = ["hp"]
    cfg.game.agent.inventory.initial = {"hp": 10}
    cfg.game.objects["enemy_station"] = GridObjectConfig(
        name="enemy_station",
        map_name="enemy_station",
        collective="clips",
        aoes={
            "territory": _weighted_territory_aoe(radius=3, alignment=AlignmentCondition.DIFFERENT_COLLECTIVE),
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
            "territory": _weighted_territory_aoe(radius=3, alignment=AlignmentCondition.SAME_COLLECTIVE),
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

    territory_at = _territory_lookup(cfg)
    assert territory_at(2, 2) == 2

    sim = Simulation(cfg)
    sim.agent(0).set_action("noop")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == 109
