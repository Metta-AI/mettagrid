"""Verify SpawnObjectMutation fires correctly from an event.

Regression test for the engine fix that sets ``ctx.target_location =
target->location`` in Event dispatch. Without that fix, SpawnObjectMutation
inside an event would try to spawn at (0, 0) instead of at the target's
cell, and the spawn would fail silently (or hit a wall).
"""

from mettagrid.config.event_config import EventConfig, periodic
from mettagrid.config.filter import query, targetHas, typeTag
from mettagrid.config.handler_config import updateTarget, withdraw
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
from mettagrid.config.mutation import SpawnObjectMutation
from mettagrid.simulator import Simulation
from mettagrid.test_support.map_builders import ObjectNameMapBuilder


def _objects_of(sim: Simulation, type_name: str) -> list[dict]:
    return [o for o in sim.grid_objects().values() if o.get("type_name") == type_name]


def test_event_spawns_object_at_target_location() -> None:
    """An event whose target is a ``crate`` fires a mutation chain that
    drains the crate's hp, removes it from the grid, then spawns a
    ``marker`` in the now-empty cell. The marker must land at the
    crate's former location (not at (0, 0))."""

    cfg = MettaGridConfig(
        game=GameConfig(
            max_steps=20,
            num_agents=1,
            obs=ObsConfig(width=3, height=3, num_tokens=100),
            resource_names=["hp"],
            actions=ActionsConfig(
                noop=NoopActionConfig(),
                move=MoveActionConfig(),
                change_vibe=ChangeVibeActionConfig(),
            ),
            objects={
                "wall": WallConfig(),
                "crate": GridObjectConfig(
                    name="crate",
                    inventory=InventoryConfig(
                        initial={"hp": 1},
                        limits={"hp": ResourceLimitsConfig(base=1, max=1, resources=["hp"])},
                    ),
                ),
                "marker": GridObjectConfig(name="marker"),
            },
            agents=[AgentConfig()],
            events={
                # Fire once on tick 0: destroy the crate and spawn a marker
                # in its cell. Event target is the crate; mutation chain runs
                # in order: drain hp, withdraw-remove (empties inventory and
                # removes target from grid), spawn marker (at target_location).
                "destroy_and_replace": EventConfig(
                    name="destroy_and_replace",
                    target_query=query(typeTag("crate"), [targetHas({"hp": 1})]),
                    timesteps=periodic(start=0, period=1, end=1),
                    mutations=[
                        updateTarget({"hp": -1}),
                        withdraw({"hp": 0}, remove_when_empty=True),
                        SpawnObjectMutation(object_type="marker"),
                    ],
                ),
            },
        )
    )
    cfg.game.map_builder = ObjectNameMapBuilder.Config(
        map_data=[
            ["wall", "wall", "wall", "wall"],
            ["wall", "agent.agent", "crate", "wall"],
            ["wall", "wall", "wall", "wall"],
        ],
    )

    sim = Simulation(cfg, seed=42)
    try:
        # Before step: crate present, no marker.
        crates_before = _objects_of(sim, "crate")
        markers_before = _objects_of(sim, "marker")
        assert len(crates_before) == 1
        assert len(markers_before) == 0
        crate_r, crate_c = crates_before[0]["r"], crates_before[0]["c"]
        assert (crate_r, crate_c) == (1, 2)

        # Step the sim once; event fires at t=0.
        sim.agent(0).set_action("noop")
        sim.step()

        # After step: crate gone, marker at (1, 2).
        crates_after = _objects_of(sim, "crate")
        markers_after = _objects_of(sim, "marker")
        assert len(crates_after) == 0, "crate should have been removed"
        assert len(markers_after) == 1, "marker should have been spawned"
        assert (markers_after[0]["r"], markers_after[0]["c"]) == (crate_r, crate_c), (
            f"marker must spawn at the crate's cell ({crate_r},{crate_c}), "
            f"got ({markers_after[0]['r']},{markers_after[0]['c']})"
        )
    finally:
        sim.close()
