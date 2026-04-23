from mettagrid.config.handler_config import Handler
from mettagrid.config.mettagrid_config import AgentConfig, GridObjectConfig, MettaGridConfig
from mettagrid.config.mutation import queryPlaceAdjacent
from mettagrid.config.query import query
from mettagrid.simulator import Simulation


def _agent_position(sim: Simulation) -> tuple[int, int]:
    for obj in sim.grid_objects(ignore_types=["wall"]).values():
        if obj.get("type_name") == "agent":
            return int(obj["r"]), int(obj["c"])
    raise AssertionError("Agent not found")


def _assert_teleport_position(cfg: MettaGridConfig, expected_position: tuple[int, int]) -> None:
    sim = Simulation(cfg, seed=0)
    try:
        sim.agent(0).set_action("move_east")
        sim.step()
        assert _agent_position(sim) == expected_position
    finally:
        sim.close()


def test_query_place_adjacent_mutation_places_actor_adjacent_to_query_result() -> None:
    cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
        [
            ["#", "#", "#", "#", "#", "#", "#", "#", "#"],
            ["#", "@", "T", ".", ".", ".", ".", ".", "#"],
            ["#", "#", "#", "#", "#", "#", "A", "#", "#"],
            ["#", "#", "#", "#", "#", "#", "#", "#", "#"],
        ],
        char_to_map_name={
            "#": "wall",
            ".": "empty",
            "@": "agent.agent",
            "T": "teleporter",
            "A": "anchor",
        },
    )
    cfg.game.objects["teleporter"] = GridObjectConfig(
        name="teleporter",
        on_use_handler=Handler(
            name="teleport",
            mutations=[queryPlaceAdjacent(query("anchor:exit"))],
        ),
    )
    cfg.game.objects["anchor"] = GridObjectConfig(name="anchor", tags=["anchor:exit"])

    _assert_teleport_position(cfg, (1, 6))


def test_query_place_adjacent_mutation_can_anchor_on_use_target() -> None:
    cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
        [
            ["#", "#", "#", "#", "#"],
            ["#", "@", "T", ".", "#"],
            ["#", "#", "#", "#", "#"],
        ],
        char_to_map_name={
            "#": "wall",
            ".": "empty",
            "@": "agent.agent",
            "T": "teleporter",
        },
    )
    cfg.game.objects["teleporter"] = GridObjectConfig(
        name="teleporter",
        tags=["anchor:exit"],
        on_use_handler=Handler(
            name="teleport",
            mutations=[queryPlaceAdjacent(query("anchor:exit"))],
        ),
    )

    _assert_teleport_position(cfg, (1, 3))


def test_query_place_adjacent_mutation_can_query_the_actor_itself() -> None:
    cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
        [
            ["#", "#", "#", "#", "#"],
            ["#", "@", "T", ".", "#"],
            ["#", ".", ".", ".", "#"],
            ["#", "#", "#", "#", "#"],
        ],
        char_to_map_name={
            "#": "wall",
            ".": "empty",
            "@": "agent.agent",
            "T": "teleporter",
        },
    )
    cfg.game.agent = AgentConfig(tags=["anchor:exit"])
    cfg.game.objects["teleporter"] = GridObjectConfig(
        name="teleporter",
        on_use_handler=Handler(
            name="teleport",
            mutations=[queryPlaceAdjacent(query("anchor:exit"))],
        ),
    )

    _assert_teleport_position(cfg, (2, 1))
