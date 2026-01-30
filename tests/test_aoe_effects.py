"""Test AOE (Area of Effect) system integration in MettaGrid.

These tests verify that:
1. AOE sources are registered when objects are created
2. AOE effects are applied to agents within range each tick
3. AOE filters (alignment, vibe, etc.) work correctly
"""

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
    ResourceLimitsConfig,
)
from mettagrid.config.mutation import updateTarget
from mettagrid.simulator import Action, Simulation


class TestAOEBasicFunctionality:
    """Test basic AOE effect application."""

    def test_aoe_effects_applied_to_agents_in_range(self):
        """Test that AOE effects are applied to agents within range.

        This test would have caught the bug where AOE system was implemented
        but not integrated into MettaGrid's step function.
        """
        # Create a simple environment with an AOE-emitting object and an agent nearby
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent at center
                ["#", ".", "S", ".", "#"],  # AOE source 1 cell away
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "aoe_source"},
        )

        cfg.game.resource_names = ["energy", "influence"]
        cfg.game.agent.inventory.initial = {"energy": 0, "influence": 0}
        cfg.game.agent.inventory.limits = {
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
            "influence": ResourceLimitsConfig(min=1000, resources=["influence"]),
        }
        # No on_tick set — no passive regen
        cfg.game.actions.noop.enabled = True

        # Create an AOE source that gives +10 energy and +5 influence per tick
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,  # Agent is 1 cell away, so within range
                    mutations=[
                        updateTarget({"energy": 10, "influence": 5}),
                    ],
                ),
            },
        )

        sim = Simulation(cfg)

        # Verify initial state
        energy_before = sim.agent(0).inventory.get("energy", 0)
        influence_before = sim.agent(0).inventory.get("influence", 0)
        assert energy_before == 0, f"Initial energy should be 0, got {energy_before}"
        assert influence_before == 0, f"Initial influence should be 0, got {influence_before}"

        # Take one step with noop action
        sim.agent(0).set_action(Action(name="noop"))
        sim.step()

        # Verify AOE effects were applied
        energy_after = sim.agent(0).inventory.get("energy", 0)
        influence_after = sim.agent(0).inventory.get("influence", 0)

        assert energy_after == 10, f"After 1 step, energy should be 10 (from AOE), got {energy_after}"
        assert influence_after == 5, f"After 1 step, influence should be 5 (from AOE), got {influence_after}"

        # Take another step to verify continuous application
        sim.agent(0).set_action(Action(name="noop"))
        sim.step()

        energy_after_2 = sim.agent(0).inventory.get("energy", 0)
        influence_after_2 = sim.agent(0).inventory.get("influence", 0)

        assert energy_after_2 == 20, f"After 2 steps, energy should be 20, got {energy_after_2}"
        assert influence_after_2 == 10, f"After 2 steps, influence should be 10, got {influence_after_2}"

    def test_aoe_effects_not_applied_outside_range(self):
        """Test that AOE effects are NOT applied to agents outside range."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#", "#", "#"],
                ["#", "@", ".", ".", ".", ".", "#"],  # Agent at (1,1)
                ["#", ".", ".", ".", ".", ".", "#"],
                ["#", ".", ".", ".", ".", ".", "#"],
                ["#", ".", ".", ".", ".", "S", "#"],  # AOE source at (5,4) - far away
                ["#", "#", "#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "aoe_source"},
        )

        cfg.game.resource_names = ["energy"]
        cfg.game.agent.inventory.initial = {"energy": 0}
        cfg.game.agent.inventory.limits = {
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
        }
        # No on_tick — no passive regen
        cfg.game.actions.noop.enabled = True

        # AOE source with radius 2 - agent is ~4 cells away (outside range)
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    mutations=[
                        updateTarget({"energy": 10}),
                    ],
                ),
            },
        )

        sim = Simulation(cfg)

        # Take one step
        sim.agent(0).set_action(Action(name="noop"))
        sim.step()

        # Verify NO AOE effects were applied (agent outside range)
        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 0, f"Agent outside AOE range should have 0 energy, got {energy}"


class TestAOEWithAlignmentFilters:
    """Test AOE effects with alignment-based filtering."""

    def test_aoe_same_collective_filter(self):
        """Test that AOE with same_collective filter only affects aligned agents."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent (cogs collective)
                ["#", ".", "S", ".", "#"],  # AOE source (cogs collective)
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "aoe_source"},
        )

        cfg.game.resource_names = ["energy"]
        cfg.game.agent.collective = "cogs"  # Agent belongs to cogs collective
        cfg.game.agent.inventory.initial = {"energy": 0}
        cfg.game.agent.inventory.limits = {
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
        }
        # No on_tick — no passive regen
        cfg.game.actions.noop.enabled = True

        # AOE source that only affects same_collective agents
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            collective="cogs",  # Same collective as agent
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[
                        AlignmentFilter(
                            target=HandlerTarget.TARGET,
                            alignment=AlignmentCondition.SAME_COLLECTIVE,
                        )
                    ],
                    mutations=[
                        updateTarget({"energy": 10}),
                    ],
                ),
            },
        )

        # Add the collective config
        cfg.game.collectives = {
            "cogs": CollectiveConfig(
                inventory=InventoryConfig(limits={"energy": ResourceLimitsConfig(min=1000, resources=["energy"])})
            ),
        }

        sim = Simulation(cfg)

        # Take one step
        sim.agent(0).set_action(Action(name="noop"))
        sim.step()

        # Agent should receive AOE effect (same collective)
        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, f"Agent in same collective should receive AOE effect, got energy={energy}"

    def test_aoe_different_collective_filter(self):
        """Test that AOE with different_collective filter only affects enemy agents."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent (cogs collective)
                ["#", ".", "S", ".", "#"],  # AOE source (clips collective - enemy)
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "aoe_source"},
        )

        cfg.game.resource_names = ["hp"]
        cfg.game.agent.collective = "cogs"
        cfg.game.agent.inventory.initial = {"hp": 100}
        cfg.game.agent.inventory.limits = {
            "hp": ResourceLimitsConfig(min=1000, resources=["hp"]),
        }
        # No on_tick — no passive regen
        cfg.game.actions.noop.enabled = True

        # Enemy AOE source that damages different_collective agents
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            collective="clips",  # Different collective from agent
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[
                        AlignmentFilter(
                            target=HandlerTarget.TARGET,
                            alignment=AlignmentCondition.DIFFERENT_COLLECTIVE,
                        )
                    ],
                    mutations=[
                        updateTarget({"hp": -10}),  # Damage
                    ],
                ),
            },
        )

        # Add collective configs
        cfg.game.collectives = {
            "cogs": CollectiveConfig(
                inventory=InventoryConfig(limits={"hp": ResourceLimitsConfig(min=1000, resources=["hp"])})
            ),
            "clips": CollectiveConfig(
                inventory=InventoryConfig(limits={"hp": ResourceLimitsConfig(min=1000, resources=["hp"])})
            ),
        }

        sim = Simulation(cfg)

        # Take one step
        sim.agent(0).set_action(Action(name="noop"))
        sim.step()

        # Agent should receive damage (different collective)
        hp = sim.agent(0).inventory.get("hp", 0)
        assert hp == 90, f"Agent in different collective should take damage, got hp={hp}"


class TestAOEMultipleSources:
    """Test AOE effects from multiple sources."""

    def test_multiple_aoe_sources_stack(self):
        """Test that effects from multiple AOE sources stack."""
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
        # No on_tick — no passive regen
        cfg.game.actions.noop.enabled = True

        # Each AOE source gives +5 energy
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    mutations=[
                        updateTarget({"energy": 5}),
                    ],
                ),
            },
        )

        sim = Simulation(cfg)

        # Take one step
        sim.agent(0).set_action(Action(name="noop"))
        sim.step()

        # Agent should receive effects from both sources (+5 + +5 = +10)
        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, f"Agent in range of 2 AOE sources should get 10 energy, got {energy}"
