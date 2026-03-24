"""Tests for move handler chain: custom handlers, beams, and blocking."""

from mettagrid.config.filter import (
    HandlerTarget,
    MaxDistanceFilter,
    ResourceFilter,
    TargetIsUsableFilter,
    TargetLocEmptyFilter,
    VibeFilter,
    isNot,
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
    RelocateMutation,
    ResourceDeltaMutation,
    SpawnObjectMutation,
    SwapMutation,
    UseTargetMutation,
)
from mettagrid.simulator import Action, Simulation
from mettagrid.test_support.actions import get_agent_position
from mettagrid.test_support.map_builders import ObjectNameMapBuilder


def _make_sim(game_config: GameConfig, map_data: list[list[str]]) -> Simulation:
    cfg = MettaGridConfig(game=game_config)
    cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=map_data)
    return Simulation(cfg, seed=42)


def _step(sim: Simulation, actions: list[Action]):
    for i, action in enumerate(actions):
        sim.agent(i).set_action(action)
    sim.step()


def _get_resource(sim: Simulation, agent_idx: int, resource_name: str) -> int:
    for _, obj_data in sim.grid_objects().items():
        if obj_data.get("agent_id") == agent_idx:
            return obj_data.get(f"inv:{resource_name}", 0)
    raise ValueError(f"Agent {agent_idx} not found")


# -- Default move handler chain (relocate, swap immobile, on-use) --

DEFAULT_MOVE_HANDLERS = [
    Handler(
        name="move",
        filters=[TargetLocEmptyFilter()],
        mutations=[RelocateMutation()],
    ),
    Handler(
        name="swap_immobile",
        filters=[
            isNot(ResourceFilter(target=HandlerTarget.TARGET, resources={"mobility": 1})),
        ],
        mutations=[SwapMutation()],
    ),
    Handler(
        name="on_use",
        filters=[TargetIsUsableFilter()],
        mutations=[UseTargetMutation()],
    ),
]


def _agent_with_mobility(team_id: int = 0) -> AgentConfig:
    return AgentConfig(
        team_id=team_id,
        inventory=InventoryConfig(
            limits={"mobility": ResourceLimitsConfig(min=1, max=1, resources=["mobility"])},
            initial={"mobility": 1},
        ),
    )


def test_basic_move_with_custom_handlers():
    """Move to empty cell using explicit handler chain works."""
    config = GameConfig(
        max_steps=50,
        num_agents=1,
        obs=ObsConfig(width=3, height=3, num_tokens=100),
        resource_names=["mobility"],
        actions=ActionsConfig(
            noop=NoopActionConfig(),
            move=MoveActionConfig(handlers=DEFAULT_MOVE_HANDLERS),
            change_vibe=ChangeVibeActionConfig(),
        ),
        objects={"wall": WallConfig()},
        agents=[_agent_with_mobility()],
    )
    map_data = [
        ["wall", "wall", "wall", "wall"],
        ["wall", "agent.red", "empty", "wall"],
        ["wall", "wall", "wall", "wall"],
    ]
    sim = _make_sim(config, map_data)

    assert get_agent_position(sim, 0) == (1, 1)

    _step(sim, [Action(name="move_east")])
    assert get_agent_position(sim, 0) == (1, 2)


def test_beam_removes_mobility_at_range():
    """Beam handler with range 5 removes target's mobility resource through empty cells."""
    config = GameConfig(
        max_steps=50,
        num_agents=2,
        obs=ObsConfig(width=3, height=3, num_tokens=100),
        resource_names=["mobility"],
        actions=ActionsConfig(
            noop=NoopActionConfig(),
            move=MoveActionConfig(
                handlers=[
                    Handler(
                        name="zap_beam",
                        filters=[
                            VibeFilter(target=HandlerTarget.ACTOR, vibe="swords"),
                            MaxDistanceFilter(target=HandlerTarget.TARGET, radius=5),
                        ],
                        mutations=[
                            ResourceDeltaMutation(target="target", deltas={"mobility": -1}),
                        ],
                    ),
                    Handler(
                        name="move",
                        filters=[TargetLocEmptyFilter()],
                        mutations=[RelocateMutation()],
                    ),
                ],
            ),
            change_vibe=ChangeVibeActionConfig(),
        ),
        objects={"wall": WallConfig()},
        agents=[_agent_with_mobility(0), _agent_with_mobility(1)],
    )
    # Agent 0 at (1,1), Agent 1 at (1,4), distance = 3 cells
    map_data = [
        ["wall", "wall", "wall", "wall", "wall", "wall"],
        ["wall", "agent.red", "empty", "empty", "agent.blue", "wall"],
        ["wall", "wall", "wall", "wall", "wall", "wall"],
    ]
    sim = _make_sim(config, map_data)

    # Both agents start with mobility=1
    assert _get_resource(sim, 1, "mobility") == 1

    # Change agent 0 vibe to swords (activates beam)
    _step(sim, [Action(name="change_vibe_swords"), Action(name="noop")])

    # Agent 0 moves east -- beam fires through empty cells and hits agent 1
    _step(sim, [Action(name="move_east"), Action(name="noop")])

    # Agent 0 should NOT have moved (beam consumed the action)
    assert get_agent_position(sim, 0) == (1, 1)
    # Agent 1 should have lost mobility
    assert _get_resource(sim, 1, "mobility") == 0


def test_beam_blocked_by_wall():
    """Beam cannot reach target through a wall."""
    config = GameConfig(
        max_steps=50,
        num_agents=2,
        obs=ObsConfig(width=3, height=3, num_tokens=100),
        resource_names=["mobility"],
        actions=ActionsConfig(
            noop=NoopActionConfig(),
            move=MoveActionConfig(
                handlers=[
                    Handler(
                        name="zap_beam",
                        filters=[
                            MaxDistanceFilter(target=HandlerTarget.TARGET, radius=5),
                        ],
                        mutations=[
                            ResourceDeltaMutation(target="target", deltas={"mobility": -1}),
                        ],
                    ),
                    Handler(
                        name="move",
                        filters=[TargetLocEmptyFilter()],
                        mutations=[RelocateMutation()],
                    ),
                ],
            ),
            change_vibe=ChangeVibeActionConfig(),
        ),
        objects={"wall": WallConfig()},
        agents=[_agent_with_mobility(0), _agent_with_mobility(1)],
    )
    # Wall between the two agents
    map_data = [
        ["wall", "wall", "wall", "wall", "wall", "wall", "wall"],
        ["wall", "agent.red", "empty", "wall", "empty", "agent.blue", "wall"],
        ["wall", "wall", "wall", "wall", "wall", "wall", "wall"],
    ]
    sim = _make_sim(config, map_data)

    # Agent 0 moves east -- beam hits the wall, not agent 1
    _step(sim, [Action(name="move_east"), Action(name="noop")])

    # Agent 1 should still have mobility (beam was blocked by wall)
    assert _get_resource(sim, 1, "mobility") == 1


def test_normal_move_when_vibe_does_not_match():
    """When beam vibe is not active, normal move works."""
    config = GameConfig(
        max_steps=50,
        num_agents=2,
        obs=ObsConfig(width=3, height=3, num_tokens=100),
        resource_names=["mobility"],
        actions=ActionsConfig(
            noop=NoopActionConfig(),
            move=MoveActionConfig(
                handlers=[
                    Handler(
                        name="zap_beam",
                        filters=[
                            VibeFilter(target=HandlerTarget.ACTOR, vibe="swords"),
                            MaxDistanceFilter(target=HandlerTarget.TARGET, radius=5),
                        ],
                        mutations=[
                            ResourceDeltaMutation(target="target", deltas={"mobility": -1}),
                        ],
                    ),
                    Handler(
                        name="move",
                        filters=[TargetLocEmptyFilter()],
                        mutations=[RelocateMutation()],
                    ),
                ],
            ),
            change_vibe=ChangeVibeActionConfig(),
        ),
        objects={"wall": WallConfig()},
        agents=[_agent_with_mobility(0), _agent_with_mobility(1)],
    )
    map_data = [
        ["wall", "wall", "wall", "wall", "wall", "wall"],
        ["wall", "agent.red", "empty", "empty", "agent.blue", "wall"],
        ["wall", "wall", "wall", "wall", "wall", "wall"],
    ]
    sim = _make_sim(config, map_data)

    # Agent 0 has default vibe (not swords) -- beam filter won't match
    _step(sim, [Action(name="move_east"), Action(name="noop")])

    # Agent 0 should have moved east
    assert get_agent_position(sim, 0) == (1, 2)
    # Agent 1 should still have mobility
    assert _get_resource(sim, 1, "mobility") == 1


def test_spawn_object_registers_tags():
    """SpawnObjectMutation creates an object and registers it with TagIndex."""
    config = GameConfig(
        max_steps=50,
        num_agents=1,
        obs=ObsConfig(width=3, height=3, num_tokens=100),
        resource_names=["stone"],
        actions=ActionsConfig(
            noop=NoopActionConfig(),
            move=MoveActionConfig(
                handlers=[
                    Handler(
                        name="build",
                        filters=[TargetLocEmptyFilter()],
                        mutations=[SpawnObjectMutation(object_type="marker")],
                    ),
                ],
            ),
            change_vibe=ChangeVibeActionConfig(),
        ),
        objects={
            "wall": WallConfig(),
            "marker": GridObjectConfig(name="marker", tags=["built"]),
        },
        agents=[AgentConfig()],
    )
    map_data = [
        ["wall", "wall", "wall", "wall"],
        ["wall", "agent.red", "empty", "wall"],
        ["wall", "wall", "wall", "wall"],
    ]
    sim = _make_sim(config, map_data)

    # Count objects before spawn
    objects_before = sim.grid_objects()
    count_before = len(objects_before)

    # Move east triggers spawn handler (target cell is empty)
    _step(sim, [Action(name="move_east")])

    # A new object should exist
    objects_after = sim.grid_objects()
    assert len(objects_after) > count_before, "SpawnObjectMutation should have created a new object"

    # Find the spawned marker
    marker = None
    for obj in objects_after.values():
        if obj.get("type_name") == "marker":
            marker = obj
            break
    assert marker is not None, "Spawned marker object should be in grid_objects"

    # Verify it has the expected tag registered
    assert marker["has_tag"] is not None, "Spawned object should expose has_tag"
