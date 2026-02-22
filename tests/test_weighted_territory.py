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
from mettagrid.config.territory_config import TerritoryConfig, TerritoryControlConfig
from mettagrid.simulator import Simulation
from mettagrid.simulator.interface import Location
from mettagrid.test_support.observation_helper import ObservationHelper


def _collective_map(*collectives: str) -> dict[str, CollectiveConfig]:
    return {name: CollectiveConfig(inventory=InventoryConfig()) for name in collectives}


def _make_territory_cfg(
    *,
    map_data: list[str],
    char_to_map_name: dict[str, str],
    agent_team: str,
    teams: tuple[str, ...] = (),
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
    cfg.game.agent.tags = [f"team:{agent_team}"]
    cfg.game.tags = [f"team:{t}" for t in teams]
    cfg.game.territories = {"team_territory": TerritoryConfig(tag_prefix="team:")}
    return cfg


def _territory_object(
    *,
    name: str,
    map_name: str,
    team: str,
    strength: int,
    tag_prefix: str = "team:",
) -> GridObjectConfig:
    return GridObjectConfig(
        name=name,
        map_name=map_name,
        tags=[f"team:{team}"],
        territory_controls=[
            TerritoryControlConfig(territory="team_territory", strength=strength),
        ],
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


@pytest.mark.parametrize("enemy_team", ["beta", "clips"])
def test_territory_midpoint_tie_stays_neutral(enemy_team: str) -> None:
    cfg = _make_territory_cfg(
        map_data=[
            ".....",
            "..E..",
            "..@..",
            "..F..",
            ".....",
        ],
        char_to_map_name={"E": "enemy_source", "F": "friendly_source"},
        agent_team="alpha",
        teams=("alpha", enemy_team),
        num_tokens=200,
    )
    cfg.game.objects["friendly_source"] = _territory_object(
        name="friendly_source",
        map_name="friendly_source",
        team="alpha",
        strength=2,
    )
    cfg.game.objects["enemy_source"] = _territory_object(
        name="enemy_source",
        map_name="enemy_source",
        team=enemy_team,
        strength=2,
    )

    territory_at = _territory_lookup(cfg)
    assert territory_at(2, 2) is None


def test_territory_at_strength_boundary() -> None:
    """Cells beyond effective radius (strength/decay) should be neutral."""
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
        agent_team="cogs",
        teams=("cogs",),
        num_tokens=300,
    )
    cfg.game.objects["friendly_source"] = _territory_object(
        name="friendly_source",
        map_name="friendly_source",
        team="cogs",
        strength=2,
    )

    territory_at = _territory_lookup(cfg)
    # (3,3) is distance 1 from (3,4) → score = max(0, 2-1) = 1 → friendly
    assert territory_at(3, 3) == 1
    # (1,4) is distance 2 from (3,4) → score = max(0, 2-2) = 0 → neutral
    assert territory_at(1, 4) is None
    # (3,6) is distance 2 from (3,4) → score = 0 → neutral
    assert territory_at(3, 6) is None


@pytest.mark.parametrize(
    ("strength", "expected_owned", "expected_neutral"),
    [
        (1, [(2, 3)], [(2, 2)]),
    ],
)
def test_small_strength_territory_coverage(
    strength: int,
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
        agent_team="cogs",
        teams=("cogs",),
        num_tokens=200,
    )
    cfg.game.objects["friendly_source"] = _territory_object(
        name="friendly_source",
        map_name="friendly_source",
        team="cogs",
        strength=strength,
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
        agent_team="cogs",
        teams=("cogs", "clips"),
        num_tokens=300,
    )
    cfg.game.objects["friendly_source"] = _territory_object(
        name="friendly_source",
        map_name="friendly_source",
        team="cogs",
        strength=3,
    )
    cfg.game.objects["enemy_source"] = _territory_object(
        name="enemy_source",
        map_name="enemy_source",
        team="clips",
        strength=3,
    )

    territory_at = _territory_lookup(cfg)
    assert territory_at(3, 3) == 2


def test_weighted_territory_influence_reaches_zero_on_boundary() -> None:
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
        agent_team="cogs",
        teams=("cogs",),
        num_tokens=300,
    )
    cfg.game.objects["friendly_source"] = _territory_object(
        name="friendly_source",
        map_name="friendly_source",
        team="cogs",
        strength=3,
    )

    territory_at = _territory_lookup(cfg)
    # (0,4) is distance 3 from (3,4) → score = max(0, 3-3) = 0 → neutral
    assert territory_at(0, 4) is None


@pytest.mark.parametrize(
    ("friendly_strength", "expected_territory"),
    [
        (5, 1),
        (2, 2),
    ],
)
def test_weighted_territory_with_different_strengths(
    friendly_strength: int,
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
        agent_team="cogs",
        teams=("cogs", "clips"),
        num_tokens=300,
    )
    cfg.game.objects["friendly_source"] = _territory_object(
        name="friendly_source",
        map_name="friendly_source",
        team="cogs",
        strength=friendly_strength,
    )
    cfg.game.objects["enemy_source"] = _territory_object(
        name="enemy_source",
        map_name="enemy_source",
        team="clips",
        strength=3,
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
        agent_team="cogs",
        teams=("cogs", "clips"),
        num_tokens=200,
    )
    cfg.game.resource_names = ["hp"]
    cfg.game.agent.inventory.initial = {"hp": 10}
    cfg.game.agent.collective = "cogs"
    cfg.game.collectives = _collective_map("cogs", "clips")
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


def test_territory_ownership_comes_from_territory_controls() -> None:
    cfg = _make_territory_cfg(
        map_data=[
            ".....",
            "..E..",
            "F.@..",
            ".....",
            ".....",
        ],
        char_to_map_name={"E": "enemy_station", "F": "friendly_station"},
        agent_team="cogs",
        teams=("cogs", "clips"),
        num_tokens=200,
    )
    cfg.game.resource_names = ["hp"]
    cfg.game.agent.inventory.initial = {"hp": 10}
    cfg.game.agent.collective = "cogs"
    cfg.game.collectives = _collective_map("cogs", "clips")
    cfg.game.objects["enemy_station"] = GridObjectConfig(
        name="enemy_station",
        map_name="enemy_station",
        tags=["team:clips"],
        collective="clips",
        territory_controls=[
            TerritoryControlConfig(territory="team_territory", strength=3),
        ],
        aoes={
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
        tags=["team:cogs"],
        collective="cogs",
        territory_controls=[
            TerritoryControlConfig(territory="team_territory", strength=3),
        ],
        aoes={
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
