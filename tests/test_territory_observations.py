import pytest

from mettagrid.config.mettagrid_config import GridObjectConfig, MettaGridConfig
from mettagrid.config.territory_config import TerritoryConfig, TerritoryControlConfig
from mettagrid.simulator import Action, Location, Simulation
from mettagrid.test_support import ObservationHelper

NEUTRAL = 0
FRIENDLY = 1
OTHER = 2
EDGE_NAMES = (
    "territory:north",
    "territory:south",
    "territory:east",
    "territory:west",
)


def _token_tile_to_neighbor_transition(token_tile_territory: int, neighbor_territory: int) -> int:
    return token_tile_territory * 3 + neighbor_territory


def _territory_here_value(obs, id_map) -> int:
    territory_here_tokens = ObservationHelper.find_global_tokens(obs, feature_id=id_map.feature_id("territory:here"))
    assert territory_here_tokens.shape[0] == 1
    return territory_here_tokens[0, 2]


def _territory_edge_tokens(obs, id_map, *, location: Location, feature_name: str):
    return ObservationHelper.find_tokens(obs, location=location, feature_id=id_map.feature_id(feature_name))


def _territory_edge_token_count(obs, id_map) -> int:
    return sum(
        ObservationHelper.find_tokens(obs, feature_id=id_map.feature_id(name), is_global=False).shape[0]
        for name in EDGE_NAMES
    )


def _territory_source(team: str, *, strength: int) -> GridObjectConfig:
    return GridObjectConfig(
        name=f"source_{team}",
        map_name=f"source_{team}",
        tags=[f"team:{team}"],
        territory_controls=[TerritoryControlConfig(territory="team_territory", strength=strength)],
    )


def _territory_sources(*teams: str) -> dict[str, GridObjectConfig]:
    if not teams:
        teams = ("cogs", "clips")
    return {f"source_{team}": _territory_source(team, strength=5) for team in teams}


def _make_territory_sim(
    map_data: list[str],
    *,
    objects: dict[str, GridObjectConfig],
    agent_team: str = "cogs",
    teams: tuple[str, ...] = ("cogs", "clips"),
    char_to_map_name: dict[str, str] | None = None,
    last_action_move: bool = False,
) -> Simulation:
    if char_to_map_name is None:
        char_to_map_name = {"F": "source_cogs", "E": "source_clips"}
    cfg = MettaGridConfig.EmptyRoom(
        num_agents=1,
        width=len(map_data[0]),
        height=len(map_data),
        border_width=0,
    ).with_ascii_map([list(row) for row in map_data], char_to_map_name=char_to_map_name)
    cfg.game.obs.width = len(map_data[0])
    cfg.game.obs.height = len(map_data)
    cfg.game.obs.num_tokens = 64
    cfg.game.obs.territory = True
    cfg.game.obs.global_obs.episode_completion_pct = False
    cfg.game.obs.global_obs.last_action = False
    cfg.game.obs.global_obs.last_action_move = last_action_move
    cfg.game.obs.global_obs.last_reward = False
    cfg.game.obs.global_obs.local_position = False
    cfg.game.agent.tags = [f"team:{agent_team}"]
    cfg.game.tags = [f"team:{team}" for team in teams]
    cfg.game.territories = {"team_territory": TerritoryConfig(tag_prefix="team:")}
    cfg.game.objects.update(objects)

    sim = Simulation(cfg, seed=0)
    sim.agent(0).set_action(Action(name="noop"))
    sim.step()
    return sim


def test_territory_observations_do_not_expose_legacy_aoe_mask_tokens() -> None:
    sim = _make_territory_sim(["F@..E"], objects=_territory_sources(), last_action_move=True)
    id_map = sim.config.game.id_map()

    assert sim.config.game.obs.aoe_mask is False
    with pytest.raises(KeyError, match="aoe_mask"):
        id_map.feature_id("aoe_mask")
    assert id_map.feature_id("last_action_move") < id_map.feature_id("territory:here")
    assert all(token.feature.name != "aoe_mask" for token in sim.agent(0).observation.tokens)


def test_territory_here_emits_global_neutral_token_when_no_cell_is_owned() -> None:
    sim = _make_territory_sim(["@"], objects={}, teams=("cogs",))
    id_map = sim.config.game.id_map()
    obs = sim._c_sim.observations()[0]

    assert _territory_here_value(obs, id_map) == NEUTRAL
    assert _territory_edge_token_count(obs, id_map) == 0


def test_hidden_corner_does_not_emit_territory_edge_tokens() -> None:
    sim = _make_territory_sim(
        [
            "E.F..",
            ".....",
            "..@..",
            ".....",
            ".....",
        ],
        objects=_territory_sources(),
    )
    id_map = sim.config.game.id_map()
    obs = sim._c_sim.observations()[0]

    top_inner = Location(row=0, col=1)
    west_edge_tokens = _territory_edge_tokens(obs, id_map, location=top_inner, feature_name="territory:west")

    assert west_edge_tokens.shape[0] == 0


@pytest.mark.parametrize(
    ("other_team", "source_char"),
    [
        ("clips", "E"),
        ("red", "R"),
        ("gold", "G"),
    ],
)
def test_territory_here_collapses_all_non_self_teams_to_other(other_team: str, source_char: str) -> None:
    sim = _make_territory_sim(
        [f".{source_char}@.."],
        objects=_territory_sources("cogs", "clips", "red", "gold"),
        teams=("cogs", "clips", "red", "gold"),
        char_to_map_name={
            "E": "source_clips",
            "R": "source_red",
            "G": "source_gold",
        },
    )
    id_map = sim.config.game.id_map()
    obs = sim._c_sim.observations()[0]

    assert _territory_here_value(obs, id_map) == OTHER, f"{other_team} should collapse to other territory"


def test_border_between_distinct_other_teams_emits_other_to_other_edge_tokens() -> None:
    sim = _make_territory_sim(
        ["R..G@...."],
        objects=_territory_sources("cogs", "red", "gold"),
        teams=("cogs", "red", "gold"),
        char_to_map_name={
            "R": "source_red",
            "G": "source_gold",
        },
    )
    id_map = sim.config.game.id_map()
    obs = sim._c_sim.observations()[0]
    center = Location(row=sim.config.game.obs.height // 2, col=sim.config.game.obs.width // 2)
    red_side = Location(row=center.row, col=center.col - 3)
    gold_side = Location(row=center.row, col=center.col - 2)

    red_edge_tokens = _territory_edge_tokens(obs, id_map, location=red_side, feature_name="territory:east")
    gold_edge_tokens = _territory_edge_tokens(obs, id_map, location=gold_side, feature_name="territory:west")

    assert red_edge_tokens.shape[0] == 1
    assert red_edge_tokens[0, 2] == _token_tile_to_neighbor_transition(OTHER, OTHER)
    assert gold_edge_tokens.shape[0] == 1
    assert gold_edge_tokens[0, 2] == _token_tile_to_neighbor_transition(OTHER, OTHER)


@pytest.mark.parametrize(
    (
        "map_data",
        "expected_here",
        "here_feature",
        "here_value",
        "neighbor_offset",
        "neighbor_feature",
        "neighbor_value",
    ),
    [
        (
            [".F@.E.."],
            FRIENDLY,
            "territory:east",
            _token_tile_to_neighbor_transition(FRIENDLY, OTHER),
            (0, 1),
            "territory:west",
            _token_tile_to_neighbor_transition(OTHER, FRIENDLY),
        ),
        (
            [".", "F", "@", ".", "E", ".", "."],
            FRIENDLY,
            "territory:south",
            _token_tile_to_neighbor_transition(FRIENDLY, OTHER),
            (1, 0),
            "territory:north",
            _token_tile_to_neighbor_transition(OTHER, FRIENDLY),
        ),
    ],
)
def test_territory_boundaries_emit_bidirectional_edge_tokens(
    map_data: list[str],
    expected_here: int,
    here_feature: str,
    here_value: int,
    neighbor_offset: tuple[int, int],
    neighbor_feature: str,
    neighbor_value: int,
) -> None:
    sim = _make_territory_sim(map_data, objects=_territory_sources())
    id_map = sim.config.game.id_map()
    obs = sim._c_sim.observations()[0]
    center = Location(row=sim.config.game.obs.height // 2, col=sim.config.game.obs.width // 2)
    neighbor = Location(row=center.row + neighbor_offset[0], col=center.col + neighbor_offset[1])

    assert _territory_here_value(obs, id_map) == expected_here

    here_tokens = _territory_edge_tokens(obs, id_map, location=center, feature_name=here_feature)
    neighbor_tokens = _territory_edge_tokens(obs, id_map, location=neighbor, feature_name=neighbor_feature)

    assert here_tokens.shape[0] == 1
    assert here_tokens[0, 2] == here_value
    assert neighbor_tokens.shape[0] == 1
    assert neighbor_tokens[0, 2] == neighbor_value
