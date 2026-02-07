"""Tests for MultiHandler dispatch modes.

Tests verify:
1. FirstMatch mode (on_use_handlers): stops after first handler where all filters pass
2. All mode (aoes): applies all handlers where filters pass
"""

from mettagrid.config.filter import actorHas, targetHas
from mettagrid.config.handler_config import AOEConfig, Handler
from mettagrid.config.mettagrid_config import (
    GridObjectConfig,
    MettaGridConfig,
    ResourceLimitsConfig,
)
from mettagrid.config.mutation import EntityTarget, ResourceDeltaMutation
from mettagrid.simulator import Simulation


class TestMultiHandlerFirstMatch:
    """Test FirstMatch (doOne) mode - stops on first successful handler.

    on_use_handlers on GridObjects use FirstMatch mode: the first handler where
    all filters pass has its mutations applied, and subsequent handlers
    are skipped.
    """

    def test_on_use_handlers_stop_after_first_match(self):
        """on_use_handlers should stop after first matching handler.

        This tests that when an agent moves onto an object with multiple
        on_use_handlers, only the first handler (in iteration order) where all
        filters pass has its mutations applied.
        """
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "C", ".", "#"],  # Chest with multiple handlers
                ["#", ".", "@", ".", "#"],  # Agent below chest
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "C": "chest"},
        )

        cfg.game.resource_names = ["gold", "silver"]
        cfg.game.agent.inventory.initial = {"gold": 0, "silver": 0}
        cfg.game.agent.inventory.limits = {
            "gold": ResourceLimitsConfig(min=1000, resources=["gold"]),
            "silver": ResourceLimitsConfig(min=1000, resources=["silver"]),
        }
        cfg.game.actions.move.enabled = True

        # Chest with two on_use_handlers - both should pass filters
        # but only first should apply (FirstMatch mode)
        cfg.game.objects["chest"] = GridObjectConfig(
            name="chest",
            map_name="chest",
            on_use_handlers={
                "give_gold": Handler(
                    filters=[],  # No filters - always passes
                    mutations=[ResourceDeltaMutation(target=EntityTarget.ACTOR, deltas={"gold": 10})],
                ),
                "give_silver": Handler(
                    filters=[],  # No filters - always passes
                    mutations=[ResourceDeltaMutation(target=EntityTarget.ACTOR, deltas={"silver": 5})],
                ),
            },
        )

        sim = Simulation(cfg)

        # Verify initial state
        gold_before = sim.agent(0).inventory.get("gold", 0)
        silver_before = sim.agent(0).inventory.get("silver", 0)
        assert gold_before == 0, f"Initial gold should be 0, got {gold_before}"
        assert silver_before == 0, f"Initial silver should be 0, got {silver_before}"

        # Move north onto the chest to trigger on_use_handlers
        sim.agent(0).set_action("move_north")
        sim.step()

        gold = sim.agent(0).inventory.get("gold", 0)
        silver = sim.agent(0).inventory.get("silver", 0)

        # FirstMatch mode: only first handler should apply
        assert gold == 10, f"Should get gold from first handler, got {gold}"
        assert silver == 0, f"Should NOT get silver (second handler skipped), got {silver}"

    def test_on_use_handlers_skip_to_second_if_first_filter_fails(self):
        """on_use_handlers should apply second handler if first handler's filter fails.

        This tests that when the first handler's filter fails, the second
        handler is tried and applied if its filters pass.
        """
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "C", ".", "#"],  # Chest with multiple handlers
                ["#", ".", "@", ".", "#"],  # Agent below chest
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "C": "chest"},
        )

        cfg.game.resource_names = ["gold", "silver", "key"]
        cfg.game.agent.inventory.initial = {"gold": 0, "silver": 0, "key": 0}  # No key!
        cfg.game.agent.inventory.limits = {
            "gold": ResourceLimitsConfig(min=1000, resources=["gold"]),
            "silver": ResourceLimitsConfig(min=1000, resources=["silver"]),
            "key": ResourceLimitsConfig(min=1000, resources=["key"]),
        }
        cfg.game.actions.move.enabled = True

        # Chest where first handler requires a key (which agent doesn't have)
        # Second handler has no filter and should apply
        cfg.game.objects["chest"] = GridObjectConfig(
            name="chest",
            map_name="chest",
            on_use_handlers={
                "give_gold_with_key": Handler(
                    filters=[actorHas({"key": 1})],  # Requires key - will fail
                    mutations=[ResourceDeltaMutation(target=EntityTarget.ACTOR, deltas={"gold": 100})],
                ),
                "give_silver_free": Handler(
                    filters=[],  # No filters - always passes
                    mutations=[ResourceDeltaMutation(target=EntityTarget.ACTOR, deltas={"silver": 5})],
                ),
            },
        )

        sim = Simulation(cfg)

        # Move north onto the chest to trigger on_use_handlers
        sim.agent(0).set_action("move_north")
        sim.step()

        gold = sim.agent(0).inventory.get("gold", 0)
        silver = sim.agent(0).inventory.get("silver", 0)

        # First handler's filter fails (no key), so second handler applies
        assert gold == 0, f"Should NOT get gold (first handler filter failed), got {gold}"
        assert silver == 5, f"Should get silver from second handler, got {silver}"


class TestMultiHandlerAll:
    """Test All (doAll) mode - applies all matching handlers.

    AOE handlers use All mode: every handler where all filters pass
    has its mutations applied.
    """

    def test_aoe_applies_all_matching_handlers(self):
        """AOE handlers should apply all handlers where filters pass."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],
                ["#", ".", "S", ".", "#"],  # Source with multiple AOEs
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "aoe_source"},
        )

        cfg.game.resource_names = ["gold", "silver"]
        cfg.game.agent.inventory.initial = {"gold": 0, "silver": 0}
        cfg.game.agent.inventory.limits = {
            "gold": ResourceLimitsConfig(min=1000, resources=["gold"]),
            "silver": ResourceLimitsConfig(min=1000, resources=["silver"]),
        }
        cfg.game.actions.noop.enabled = True

        # AOE source with multiple AOE configs - all should apply
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "give_gold": AOEConfig(
                    radius=2,
                    filters=[],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"gold": 10})],
                ),
                "give_silver": AOEConfig(
                    radius=2,
                    filters=[],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"silver": 5})],
                ),
            },
        )

        sim = Simulation(cfg)

        # Verify initial state
        gold_before = sim.agent(0).inventory.get("gold", 0)
        silver_before = sim.agent(0).inventory.get("silver", 0)
        assert gold_before == 0, f"Initial gold should be 0, got {gold_before}"
        assert silver_before == 0, f"Initial silver should be 0, got {silver_before}"

        sim.agent(0).set_action("noop")
        sim.step()

        gold = sim.agent(0).inventory.get("gold", 0)
        silver = sim.agent(0).inventory.get("silver", 0)

        # All mode: both handlers should apply
        assert gold == 10, f"Should get gold from first AOE, got {gold}"
        assert silver == 5, f"Should get silver from second AOE, got {silver}"

    def test_aoe_applies_only_matching_handlers(self):
        """AOE handlers should only apply handlers where filters pass.

        This tests that in All mode, handlers with failing filters are
        skipped but other matching handlers still apply.
        """
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],
                ["#", ".", "S", ".", "#"],  # Source with multiple AOEs
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "aoe_source"},
        )

        cfg.game.resource_names = ["gold", "silver", "key"]
        cfg.game.agent.inventory.initial = {"gold": 0, "silver": 0, "key": 0}  # No key
        cfg.game.agent.inventory.limits = {
            "gold": ResourceLimitsConfig(min=1000, resources=["gold"]),
            "silver": ResourceLimitsConfig(min=1000, resources=["silver"]),
            "key": ResourceLimitsConfig(min=1000, resources=["key"]),
        }
        cfg.game.actions.noop.enabled = True

        # AOE source where one AOE requires a key (which agent doesn't have)
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "give_gold_with_key": AOEConfig(
                    radius=2,
                    filters=[targetHas({"key": 1})],  # Requires key - will fail
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"gold": 100})],
                ),
                "give_silver_free": AOEConfig(
                    radius=2,
                    filters=[],  # No filters - always passes
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"silver": 5})],
                ),
            },
        )

        sim = Simulation(cfg)
        sim.agent(0).set_action("noop")
        sim.step()

        gold = sim.agent(0).inventory.get("gold", 0)
        silver = sim.agent(0).inventory.get("silver", 0)

        # All mode: only the handler without filter should apply
        assert gold == 0, f"Should NOT get gold (filter failed), got {gold}"
        assert silver == 5, f"Should get silver from second AOE, got {silver}"

    def test_aoe_stacks_multiple_sources(self):
        """Multiple AOE sources should all apply their effects.

        This tests that All mode applies across multiple AOE sources,
        not just within a single source.
        """
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", "S", ".", "S", "#"],  # Two AOE sources
                ["#", ".", "@", ".", "#"],  # Agent in range of both
                ["#", ".", ".", ".", "#"],
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "aoe_source"},
        )

        cfg.game.resource_names = ["energy"]
        cfg.game.agent.inventory.initial = {"energy": 0}
        cfg.game.agent.inventory.limits = {
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
        }
        cfg.game.actions.noop.enabled = True

        # Each AOE source gives +5 energy
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "give_energy": AOEConfig(
                    radius=2,
                    filters=[],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 5})],
                ),
            },
        )

        sim = Simulation(cfg)
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)

        # Agent should receive effects from both sources (+5 + +5 = +10)
        assert energy == 10, f"Agent in range of 2 AOE sources should get 10 energy, got {energy}"
