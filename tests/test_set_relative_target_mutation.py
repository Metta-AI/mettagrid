"""Tests for the SetRelativeTargetMutation primitive.

SetRelativeTarget writes ``ctx.target_location = actor + dir * dist`` so
that subsequent mutations can act on that cell. The canonical pairing
is with ``RelocateMutation`` to move the actor (useful from
event/AOE/onUse handlers that want to move agents without going
through the move action).
"""

import pytest

from mettagrid.config.event_config import EventConfig, periodic
from mettagrid.config.filter import query, typeTag
from mettagrid.config.mettagrid_c_config import convert_to_cpp_game_config
from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    AgentConfig,
    ChangeVibeActionConfig,
    GameConfig,
    MettaGridConfig,
    MoveActionConfig,
    NoopActionConfig,
    ObsConfig,
    WallConfig,
)
from mettagrid.config.mutation import (
    RelocateMutation,
    SetRelativeTargetMutation,
)
from mettagrid.mettagrid_c import MettaGrid
from mettagrid.mettagrid_c import SetRelativeTargetMutationConfig as CppSetRelativeTargetMutationConfig
from mettagrid.simulator import Simulation
from mettagrid.test_support.actions import get_agent_position
from mettagrid.test_support.map_builders import ObjectNameMapBuilder


def _make_event_sim(
    map_data: list[list[str]],
    direction: str,
    distance: int = 1,
    fire_at: int = 0,
) -> Simulation:
    """Build a sim with a single event that shoves matching agents one
    step in ``direction`` via SetRelativeTarget + Relocate."""
    cfg = MettaGridConfig(
        game=GameConfig(
            max_steps=20,
            num_agents=1,
            obs=ObsConfig(width=3, height=3, num_tokens=100),
            resource_names=[],
            actions=ActionsConfig(
                noop=NoopActionConfig(),
                move=MoveActionConfig(),
                change_vibe=ChangeVibeActionConfig(),
            ),
            objects={"wall": WallConfig()},
            agents=[AgentConfig()],
            events={
                "shove": EventConfig(
                    name="shove",
                    target_query=query(typeTag("agent")),
                    timesteps=periodic(start=fire_at, period=1, end=fire_at),
                    mutations=[
                        SetRelativeTargetMutation(direction=direction, distance=distance),
                        RelocateMutation(),
                    ],
                ),
            },
        )
    )
    cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=map_data)
    return Simulation(cfg, seed=42)


def test_event_moves_agent_north() -> None:
    """Event with SetRelativeTarget("north") + Relocate moves the agent
    one cell north."""
    map_data = [
        ["wall", "wall", "wall"],
        ["wall", "empty", "wall"],
        ["wall", "agent.agent", "wall"],
        ["wall", "wall", "wall"],
    ]
    sim = _make_event_sim(map_data, direction="north")
    try:
        assert get_agent_position(sim, 0) == (2, 1)
        sim.agent(0).set_action("noop")
        sim.step()
        assert get_agent_position(sim, 0) == (1, 1), "agent should have moved one cell north"
    finally:
        sim.close()


def test_event_moves_agent_south() -> None:
    """South direction also moves the agent correctly."""
    map_data = [
        ["wall", "wall", "wall"],
        ["wall", "agent.agent", "wall"],
        ["wall", "empty", "wall"],
        ["wall", "wall", "wall"],
    ]
    sim = _make_event_sim(map_data, direction="south")
    try:
        assert get_agent_position(sim, 0) == (1, 1)
        sim.agent(0).set_action("noop")
        sim.step()
        assert get_agent_position(sim, 0) == (2, 1), "agent should have moved one cell south"
    finally:
        sim.close()


def test_event_moves_agent_east() -> None:
    map_data = [
        ["wall", "wall", "wall", "wall"],
        ["wall", "agent.agent", "empty", "wall"],
        ["wall", "wall", "wall", "wall"],
    ]
    sim = _make_event_sim(map_data, direction="east")
    try:
        assert get_agent_position(sim, 0) == (1, 1)
        sim.agent(0).set_action("noop")
        sim.step()
        assert get_agent_position(sim, 0) == (1, 2)
    finally:
        sim.close()


def test_event_moves_agent_west() -> None:
    map_data = [
        ["wall", "wall", "wall", "wall"],
        ["wall", "empty", "agent.agent", "wall"],
        ["wall", "wall", "wall", "wall"],
    ]
    sim = _make_event_sim(map_data, direction="west")
    try:
        assert get_agent_position(sim, 0) == (1, 2)
        sim.agent(0).set_action("noop")
        sim.step()
        assert get_agent_position(sim, 0) == (1, 1)
    finally:
        sim.close()


def test_event_moves_agent_distance_two() -> None:
    """distance=2 writes target_location two cells away."""
    map_data = [
        ["wall", "wall", "wall"],
        ["wall", "empty", "wall"],
        ["wall", "empty", "wall"],
        ["wall", "agent.agent", "wall"],
        ["wall", "wall", "wall"],
    ]
    sim = _make_event_sim(map_data, direction="north", distance=2)
    try:
        assert get_agent_position(sim, 0) == (3, 1)
        sim.agent(0).set_action("noop")
        sim.step()
        assert get_agent_position(sim, 0) == (1, 1), "distance=2 should skip to two cells north"
    finally:
        sim.close()


def test_event_moves_agent_diagonally() -> None:
    """Diagonal directions work (northeast, etc.)."""
    map_data = [
        ["wall", "wall", "wall", "wall"],
        ["wall", "empty", "empty", "wall"],
        ["wall", "agent.agent", "empty", "wall"],
        ["wall", "wall", "wall", "wall"],
    ]
    sim = _make_event_sim(map_data, direction="northeast")
    try:
        assert get_agent_position(sim, 0) == (2, 1)
        sim.agent(0).set_action("noop")
        sim.step()
        assert get_agent_position(sim, 0) == (1, 2), "NE should move (-1, +1)"
    finally:
        sim.close()


def test_event_move_blocked_by_wall_leaves_agent_in_place() -> None:
    """When the target cell is a wall, RelocateMutation fails and the
    agent stays put (SetRelativeTarget itself does not fail on
    occupied cells — it just writes the location)."""
    map_data = [
        ["wall", "wall", "wall"],
        ["wall", "agent.agent", "wall"],
        ["wall", "wall", "wall"],
    ]
    sim = _make_event_sim(map_data, direction="north")
    try:
        assert get_agent_position(sim, 0) == (1, 1)
        sim.agent(0).set_action("noop")
        sim.step()
        assert get_agent_position(sim, 0) == (1, 1), "agent should not move through wall"
    finally:
        sim.close()


def test_cpp_constructor_rejects_out_of_range_direction() -> None:
    """The C++ constructor bounds-checks ``direction`` (0..7) so a hand-
    built CppSetRelativeTargetMutationConfig that bypasses the Python
    ``Literal`` type fails loudly at handler construction time instead
    of indexing past the orientation delta tables at apply() time."""
    # Build a valid sim that already has a ``shove`` event in its C++ game
    # config, then inject a bad direction into the C++ mutation on that
    # event before passing the config into MettaGrid.
    cfg = MettaGridConfig(
        game=GameConfig(
            max_steps=5,
            num_agents=1,
            obs=ObsConfig(width=3, height=3, num_tokens=100),
            resource_names=[],
            actions=ActionsConfig(
                noop=NoopActionConfig(),
                move=MoveActionConfig(),
                change_vibe=ChangeVibeActionConfig(),
            ),
            objects={"wall": WallConfig()},
            agents=[AgentConfig()],
            events={
                "shove": EventConfig(
                    name="shove",
                    target_query=query(typeTag("agent")),
                    timesteps=periodic(start=0, period=1, end=0),
                    mutations=[
                        SetRelativeTargetMutation(direction="north"),
                        RelocateMutation(),
                    ],
                ),
            },
        )
    )
    cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=[["agent.agent"]])

    c_cfg, _ = convert_to_cpp_game_config(cfg.game)
    bad_mutation = CppSetRelativeTargetMutationConfig()
    bad_mutation.direction = 8  # out of [0, 7]
    bad_mutation.distance = 1
    c_cfg.events["shove"].add_set_relative_target_mutation(bad_mutation)

    with pytest.raises(RuntimeError, match="direction must be in"):
        MettaGrid(c_cfg, [["agent.agent"]], 0)


def test_event_move_off_grid_is_safe() -> None:
    """When direction*distance leaves the grid, the mutation fails and
    the agent stays put (no crash, no wrap)."""
    # Agent is at the top edge of the inner area; pushing north lands
    # on a wall, pushing 10 cells north would also go off the edge of
    # a 3-row map if we had no walls.
    map_data = [
        ["agent.agent"],
    ]
    sim = _make_event_sim(map_data, direction="north", distance=5)
    try:
        assert get_agent_position(sim, 0) == (0, 0)
        sim.agent(0).set_action("noop")
        sim.step()
        assert get_agent_position(sim, 0) == (0, 0), "agent should stay when target is off-grid"
    finally:
        sim.close()
