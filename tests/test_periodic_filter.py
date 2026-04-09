"""Tests for PeriodicFilter on game-level on_tick handlers.

Verifies that PeriodicFilter gates handler execution to specific timestep intervals.
"""

from mettagrid.config.filter.periodic_filter import PeriodicFilter
from mettagrid.config.handler_config import Handler
from mettagrid.config.mettagrid_config import (
    GridObjectConfig,
    InventoryConfig,
    MettaGridConfig,
    ResourceLimitsConfig,
)
from mettagrid.config.mutation.query_inventory_mutation import queryDelta
from mettagrid.config.query import query
from mettagrid.config.tag import typeTag
from mettagrid.simulator import Simulation


def _make_sim_with_periodic_on_tick(period: int, start_on: int | None = None) -> Simulation:
    """Create a simulation with a game-level on_tick handler gated by PeriodicFilter.

    Places an agent and a chest. The on_tick handler adds 10 gold to the chest every `period` ticks.
    """
    cfg = MettaGridConfig.EmptyRoom(num_agents=1, width=5, height=5, border_width=0).with_ascii_map(
        [
            ["@", ".", ".", ".", "."],
            [".", "C", ".", ".", "."],
            [".", ".", ".", ".", "."],
            [".", ".", ".", ".", "."],
            [".", ".", ".", ".", "."],
        ],
        char_to_map_name={"@": "agent.agent", ".": "empty", "C": "chest"},
    )
    cfg.game.resource_names = ["gold"]
    cfg.game.agent.inventory.initial = {"gold": 0}
    cfg.game.agent.inventory.limits = {
        "gold": ResourceLimitsConfig(base=1000, resources=["gold"]),
    }
    cfg.game.objects["chest"] = GridObjectConfig(
        name="chest",
        map_name="chest",
        inventory=InventoryConfig(initial={"gold": 0}, default_limit=1000),
    )
    cfg.game.actions.noop.enabled = True

    pf = PeriodicFilter(period=period) if start_on is None else PeriodicFilter(period=period, start_on=start_on)
    cfg.game.on_tick["refill_chest"] = Handler(
        filters=[pf],
        mutations=[queryDelta(query(typeTag("chest")), {"gold": 10})],
    )

    return Simulation(cfg, seed=42)


def _chest_gold(sim: Simulation) -> int:
    gold_idx = sim.resource_names.index("gold")
    for obj in sim.grid_objects().values():
        if obj.get("type_name") == "chest":
            return obj.get("inventory", {}).get(gold_idx, 0)
    return 0


class TestPeriodicFilter:
    def test_fires_at_period(self):
        """Handler should fire exactly at period boundaries."""
        sim = _make_sim_with_periodic_on_tick(period=5)

        # Steps 1-4: no fire
        for _ in range(4):
            sim.agent(0).set_action("noop")
            sim.step()
        assert _chest_gold(sim) == 0

        # Step 5: fires (default start_on = period)
        sim.agent(0).set_action("noop")
        sim.step()
        assert _chest_gold(sim) == 10

        # Steps 6-9: no fire
        for _ in range(4):
            sim.agent(0).set_action("noop")
            sim.step()
        assert _chest_gold(sim) == 10

        # Step 10: fires again
        sim.agent(0).set_action("noop")
        sim.step()
        assert _chest_gold(sim) == 20

        sim.close()

    def test_custom_start_on(self):
        """Handler with start_on=3 should first fire at step 3."""
        sim = _make_sim_with_periodic_on_tick(period=5, start_on=3)

        # Steps 1-2: no fire
        for _ in range(2):
            sim.agent(0).set_action("noop")
            sim.step()
        assert _chest_gold(sim) == 0

        # Step 3: fires (start_on=3)
        sim.agent(0).set_action("noop")
        sim.step()
        assert _chest_gold(sim) == 10

        # Steps 4-7: no fire
        for _ in range(4):
            sim.agent(0).set_action("noop")
            sim.step()
        assert _chest_gold(sim) == 10

        # Step 8: fires (3 + 5 = 8)
        sim.agent(0).set_action("noop")
        sim.step()
        assert _chest_gold(sim) == 20

        sim.close()

    def test_period_1_fires_every_tick(self):
        """Period=1 should fire every single tick."""
        sim = _make_sim_with_periodic_on_tick(period=1, start_on=1)

        for i in range(10):
            sim.agent(0).set_action("noop")
            sim.step()
            assert _chest_gold(sim) == (i + 1) * 10

        sim.close()

    def test_inventory_capped_by_limit(self):
        """queryDelta should not push inventory past the object's limit."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, width=5, height=5, border_width=0).with_ascii_map(
            [
                ["@", ".", ".", ".", "."],
                [".", "C", ".", ".", "."],
                [".", ".", ".", ".", "."],
                [".", ".", ".", ".", "."],
                [".", ".", ".", ".", "."],
            ],
            char_to_map_name={"@": "agent.agent", ".": "empty", "C": "chest"},
        )
        cfg.game.resource_names = ["gold"]
        cfg.game.agent.inventory.initial = {"gold": 0}
        cfg.game.agent.inventory.limits = {
            "gold": ResourceLimitsConfig(base=1000, resources=["gold"]),
        }
        cfg.game.objects["chest"] = GridObjectConfig(
            name="chest",
            map_name="chest",
            inventory=InventoryConfig(initial={"gold": 80}, default_limit=100),
        )
        cfg.game.actions.noop.enabled = True
        cfg.game.on_tick["refill"] = Handler(
            filters=[PeriodicFilter(period=1, start_on=1)],
            mutations=[queryDelta(query(typeTag("chest")), {"gold": 50})],
        )

        sim = Simulation(cfg, seed=42)

        assert _chest_gold(sim) == 80

        # Step 1: try to add 50, but capped at 100
        sim.agent(0).set_action("noop")
        sim.step()
        assert _chest_gold(sim) == 100

        # Step 2: already at cap, stays at 100
        sim.agent(0).set_action("noop")
        sim.step()
        assert _chest_gold(sim) == 100

        sim.close()
