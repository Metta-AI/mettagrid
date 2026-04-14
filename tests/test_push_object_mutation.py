"""Tests for the PushObjectMutation C++ primitive.

PushObjectMutation pushes ctx.target one cell further along the
actor->target direction, failing if the destination is off-grid or
occupied. Tested here via a custom move handler that kicks a "box"
object one cell forward.
"""

from mettagrid.config.filter import (
    HandlerTarget,
    MaxDistanceFilter,
    TargetLocEmptyFilter,
    isA,
)
from mettagrid.config.handler_config import Handler
from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    AgentConfig,
    ChangeVibeActionConfig,
    GameConfig,
    GridObjectConfig,
    InventoryConfig,
    MettaGridConfig,
    MoveActionConfig,
    NoopActionConfig,
    ObsConfig,
    ResourceLimitsConfig,
    WallConfig,
)
from mettagrid.config.mutation import (
    PushObjectMutation,
    RelocateMutation,
)
from mettagrid.simulator import Action, Simulation
from mettagrid.test_support.actions import get_agent_position
from mettagrid.test_support.map_builders import ObjectNameMapBuilder

KICK_HANDLERS = [
    Handler(
        name="kick_box",
        filters=[isA("box")],
        mutations=[PushObjectMutation(), RelocateMutation()],
    ),
    Handler(
        name="move",
        filters=[TargetLocEmptyFilter()],
        mutations=[RelocateMutation()],
    ),
]


def _base_config() -> GameConfig:
    return GameConfig(
        max_steps=50,
        num_agents=1,
        obs=ObsConfig(width=3, height=3, num_tokens=100),
        resource_names=["mobility"],
        actions=ActionsConfig(
            noop=NoopActionConfig(),
            move=MoveActionConfig(handlers=KICK_HANDLERS),
            change_vibe=ChangeVibeActionConfig(),
        ),
        objects={
            "wall": WallConfig(),
            "box": GridObjectConfig(
                name="box",
                inventory=InventoryConfig(
                    initial={"mobility": 1},
                    limits={"mobility": ResourceLimitsConfig(base=1, max=1, resources=["mobility"])},
                ),
            ),
        },
        agents=[
            AgentConfig(
                team_id=0,
                inventory=InventoryConfig(
                    limits={"mobility": ResourceLimitsConfig(base=1, max=1, resources=["mobility"])},
                    initial={"mobility": 1},
                ),
            ),
        ],
    )


def _make_sim(map_data: list[list[str]]) -> Simulation:
    cfg = MettaGridConfig(game=_base_config())
    cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=map_data)
    return Simulation(cfg, seed=42)


def _make_diagonal_sim(map_data: list[list[str]]) -> Simulation:
    """Variant of _make_sim that also allows diagonal move actions."""
    cfg = MettaGridConfig(game=_base_config())
    cfg.game.actions.move = MoveActionConfig(
        handlers=KICK_HANDLERS,
        allowed_directions=[
            "north",
            "south",
            "west",
            "east",
            "northwest",
            "northeast",
            "southwest",
            "southeast",
        ],
    )
    cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=map_data)
    return Simulation(cfg, seed=42)


def _make_ranged_kick_sim(map_data: list[list[str]], radius: int) -> Simulation:
    """Variant that allows the kick handler to reach across empty cells.

    Uses a MaxDistanceFilter so the move action line-scans past empty
    cells and fires the kick on the first box within ``radius``. This
    lets a test force actor/target separations > 1 to exercise the
    direction-clamping in PushObjectMutation.
    """
    cfg = MettaGridConfig(game=_base_config())
    cfg.game.actions.move = MoveActionConfig(
        handlers=[
            Handler(
                name="kick_box_ranged",
                filters=[
                    isA("box"),
                    MaxDistanceFilter(target=HandlerTarget.TARGET, radius=radius),
                ],
                mutations=[PushObjectMutation(), RelocateMutation()],
            ),
            Handler(
                name="move",
                filters=[TargetLocEmptyFilter()],
                mutations=[RelocateMutation()],
            ),
        ],
    )
    cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=map_data)
    return Simulation(cfg, seed=42)


def _object_positions(sim: Simulation, type_name: str) -> list[tuple[int, int]]:
    return [(o["r"], o["c"]) for o in sim.grid_objects().values() if o.get("type_name") == type_name]


def test_push_box_into_empty_cell() -> None:
    """Agent east of empty, box east of agent, empty east of box. Agent
    moves east: the box is pushed one cell east and the agent moves
    forward into the vacated cell."""
    # Row layout: [wall, agent, box, empty, wall]
    map_data = [
        ["wall", "wall", "wall", "wall", "wall"],
        ["wall", "agent.red", "box", "empty", "wall"],
        ["wall", "wall", "wall", "wall", "wall"],
    ]
    sim = _make_sim(map_data)
    try:
        assert get_agent_position(sim, 0) == (1, 1)
        assert _object_positions(sim, "box") == [(1, 2)]

        sim.agent(0).set_action(Action(name="move_east"))
        sim.step()

        # Agent moved into (1,2), box shoved into (1,3).
        assert get_agent_position(sim, 0) == (1, 2), "agent should step into vacated box cell"
        assert _object_positions(sim, "box") == [(1, 3)], "box should be pushed one cell east"
    finally:
        sim.close()


def test_push_box_into_wall_fails() -> None:
    """Box is adjacent to a wall. PushObjectMutation fails; the kick
    handler aborts; the fallback ``move`` handler also fails (box occupies
    target). Agent and box stay put."""
    map_data = [
        ["wall", "wall", "wall", "wall"],
        ["wall", "agent.red", "box", "wall"],
        ["wall", "wall", "wall", "wall"],
    ]
    sim = _make_sim(map_data)
    try:
        start_agent = get_agent_position(sim, 0)
        start_box = _object_positions(sim, "box")

        sim.agent(0).set_action(Action(name="move_east"))
        sim.step()

        assert get_agent_position(sim, 0) == start_agent, "agent should not move when box is against wall"
        assert _object_positions(sim, "box") == start_box, "box should not move into wall"
    finally:
        sim.close()


def test_push_box_into_other_box_fails() -> None:
    """Two boxes in a row — pushing the first should fail because the
    destination cell is occupied by the second box."""
    map_data = [
        ["wall", "wall", "wall", "wall", "wall"],
        ["wall", "agent.red", "box", "box", "wall"],
        ["wall", "wall", "wall", "wall", "wall"],
    ]
    sim = _make_sim(map_data)
    try:
        start_agent = get_agent_position(sim, 0)
        start_boxes = sorted(_object_positions(sim, "box"))

        sim.agent(0).set_action(Action(name="move_east"))
        sim.step()

        assert get_agent_position(sim, 0) == start_agent, "agent should not move"
        assert sorted(_object_positions(sim, "box")) == start_boxes, "no box should have moved"
    finally:
        sim.close()


def test_push_box_south() -> None:
    """Push works in the south direction too (not just east)."""
    map_data = [
        ["wall", "wall", "wall", "wall"],
        ["wall", "agent.red", "empty", "wall"],
        ["wall", "box", "empty", "wall"],
        ["wall", "empty", "empty", "wall"],
        ["wall", "wall", "wall", "wall"],
    ]
    sim = _make_sim(map_data)
    try:
        assert get_agent_position(sim, 0) == (1, 1)
        assert _object_positions(sim, "box") == [(2, 1)]

        sim.agent(0).set_action(Action(name="move_south"))
        sim.step()

        assert get_agent_position(sim, 0) == (2, 1), "agent should step south into vacated cell"
        assert _object_positions(sim, "box") == [(3, 1)], "box should be pushed one cell south"
    finally:
        sim.close()


def test_push_box_diagonally() -> None:
    """Agent and box are diagonal neighbours. A diagonal move kicks the
    box diagonally by one cell and the agent steps into the vacated cell.

    Layout (agent at (3,1), box at (2,2), empty at (1,3)):
        # # # # #
        # . . . #
        # . B . #
        # @ . . #
        # # # # #

    On move_northeast, the line-scan finds the box at (2,2). The kick
    handler fires with actor=(3,1), target=(2,2). PushObjectMutation's
    clamped direction is (dr=-1, dc=+1), so the box goes to (1,3).
    RelocateMutation then moves the agent to (2,2).
    """
    map_data = [
        ["wall", "wall", "wall", "wall", "wall"],
        ["wall", "empty", "empty", "empty", "wall"],
        ["wall", "empty", "box", "empty", "wall"],
        ["wall", "agent.red", "empty", "empty", "wall"],
        ["wall", "wall", "wall", "wall", "wall"],
    ]
    sim = _make_diagonal_sim(map_data)
    try:
        assert get_agent_position(sim, 0) == (3, 1)
        assert _object_positions(sim, "box") == [(2, 2)]

        sim.agent(0).set_action(Action(name="move_northeast"))
        sim.step()

        assert get_agent_position(sim, 0) == (2, 2), "agent should step diagonally into vacated box cell"
        assert _object_positions(sim, "box") == [(1, 3)], "box should be pushed diagonally one cell"
    finally:
        sim.close()


def test_push_clamps_to_unit_step_when_actor_is_far() -> None:
    """Clamping check: with a ranged kick handler (MaxDistanceFilter
    radius=3), the agent can reach a box three cells away. Without
    clamping, PushObjectMutation would shove the box three cells forward
    (proportional to actor/target distance). With clamping, the box
    moves by exactly one cell.

    Layout: [wall, agent, empty, empty, box, empty, empty, wall]
                        ^^^^^^^^^^^^^ scan past  ^^^ box pushed here

    With clamping, box at (1,4) goes to (1,5).
    Without clamping, it would land at (1,7) (a wall) and the push would
    fail instead, so the test wouldn't observe the box at any new position.
    """
    map_data = [
        ["wall", "wall", "wall", "wall", "wall", "wall", "wall", "wall"],
        ["wall", "agent.red", "empty", "empty", "box", "empty", "empty", "wall"],
        ["wall", "wall", "wall", "wall", "wall", "wall", "wall", "wall"],
    ]
    sim = _make_ranged_kick_sim(map_data, radius=3)
    try:
        assert get_agent_position(sim, 0) == (1, 1)
        assert _object_positions(sim, "box") == [(1, 4)]

        sim.agent(0).set_action(Action(name="move_east"))
        sim.step()

        # Agent relocates to the box's former cell (target_location=(1,4)).
        assert get_agent_position(sim, 0) == (1, 4), "agent should relocate to target_location (the box's former cell)"
        # Box moved by exactly one cell east thanks to the clamp.
        assert _object_positions(sim, "box") == [(1, 5)], (
            "box should be pushed by exactly one cell, not by the full 3-cell actor/target distance"
        )
    finally:
        sim.close()
