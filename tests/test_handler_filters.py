"""Tests for handler filters (vibe, resource, alignment) on AOE handlers.

These tests verify that:
1. VibeFilter correctly gates handler execution based on entity vibe
2. AlignmentFilter correctly gates handler execution based on collective alignment
"""

from mettagrid.config.filter import AlignmentFilter, targetVibe
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
from mettagrid.config.mutation import (
    EntityTarget,
    ResourceDeltaMutation,
)
from mettagrid.simulator import Simulation


class TestVibeFilterOnAOE:
    """Test vibe filter on AOE handlers."""

    def test_aoe_handler_with_vibe_filter_only_affects_matching_vibe(self):
        """AOE handler with vibe filter should only affect entities with matching vibe."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent
                ["#", ".", "S", ".", "#"],  # AOE source
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

        # AOE source with vibe filter - only affects agents with "charger" vibe
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[targetVibe("charger")],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        # Step without charger vibe - should NOT get energy
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 0, f"Should NOT get energy without charger vibe, got {energy}"

        # Change vibe to charger - AOE fires at end of this step too (agent now has charger vibe)
        sim.agent(0).set_action("change_vibe_charger")
        sim.step()

        # After changing vibe, the AOE should have fired once (during change_vibe step)
        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, f"Should get energy after changing to charger vibe, got {energy}"

        # Step with charger vibe - should get more energy
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 20, f"Should have 20 energy after second step with charger vibe, got {energy}"

    def test_aoe_handler_without_vibe_filter_affects_all(self):
        """AOE handler without vibe filter should affect all entities in range."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent
                ["#", ".", "S", ".", "#"],  # AOE source
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

        # AOE source without vibe filter - affects all agents
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[],  # No filter
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        # Step without any special vibe - should still get energy
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, f"Should get energy without vibe filter, got {energy}"

    def test_aoe_vibe_filter_with_different_vibe_does_not_trigger(self):
        """AOE handler should not trigger if agent has different vibe than filter requires."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent
                ["#", ".", "S", ".", "#"],  # AOE source
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

        # AOE source that requires "charger" vibe
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[targetVibe("charger")],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        # Change to "up" vibe (not charger)
        sim.agent(0).set_action("change_vibe_up")
        sim.step()

        # Step with "up" vibe - should NOT get energy (filter requires "charger")
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 0, f"Should NOT get energy with wrong vibe, got {energy}"


class TestAlignmentFilterOnAOE:
    """Test alignment filter on AOE handlers."""

    def test_aoe_alignment_filter_same_collective(self):
        """AOE with same_collective filter should only affect aligned agents."""
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

        # Define collectives
        cfg.game.collectives = {
            "cogs": CollectiveConfig(
                inventory=InventoryConfig(limits={"energy": ResourceLimitsConfig(min=10000, resources=["energy"])})
            ),
        }

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
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        # Step - agent and AOE source are in same collective
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, f"Agent in same collective should receive AOE effect, got energy={energy}"

    def test_aoe_alignment_filter_different_collective_blocks(self):
        """AOE with same_collective filter should NOT affect agents in different collective."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent (cogs collective)
                ["#", ".", "S", ".", "#"],  # AOE source (clips collective)
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

        # Define collectives
        cfg.game.collectives = {
            "cogs": CollectiveConfig(
                inventory=InventoryConfig(limits={"energy": ResourceLimitsConfig(min=10000, resources=["energy"])})
            ),
            "clips": CollectiveConfig(
                inventory=InventoryConfig(limits={"energy": ResourceLimitsConfig(min=10000, resources=["energy"])})
            ),
        }

        # AOE source that only affects same_collective agents (but source is clips)
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
                            alignment=AlignmentCondition.SAME_COLLECTIVE,
                        )
                    ],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        # Step - agent is cogs, AOE source is clips, should NOT receive effect
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 0, f"Agent in different collective should NOT receive AOE effect, got energy={energy}"

    def test_aoe_alignment_filter_different_collective_damages(self):
        """AOE with different_collective filter should affect agents in different collective."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent (cogs collective)
                ["#", ".", "S", ".", "#"],  # AOE source (clips collective)
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "aoe_source"},
        )

        cfg.game.resource_names = ["hp"]
        cfg.game.agent.collective = "cogs"  # Agent belongs to cogs collective
        cfg.game.agent.inventory.initial = {"hp": 100}
        cfg.game.agent.inventory.limits = {
            "hp": ResourceLimitsConfig(min=1000, resources=["hp"]),
        }
        # No on_tick — no passive regen
        cfg.game.actions.noop.enabled = True

        # Define collectives
        cfg.game.collectives = {
            "cogs": CollectiveConfig(
                inventory=InventoryConfig(limits={"hp": ResourceLimitsConfig(min=10000, resources=["hp"])})
            ),
            "clips": CollectiveConfig(
                inventory=InventoryConfig(limits={"hp": ResourceLimitsConfig(min=10000, resources=["hp"])})
            ),
        }

        # AOE source that damages different_collective agents
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
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"hp": -10})],
                )
            },
        )

        sim = Simulation(cfg)

        # Step - agent is cogs, AOE source is clips, should receive damage
        sim.agent(0).set_action("noop")
        sim.step()

        hp = sim.agent(0).inventory.get("hp", 0)
        assert hp == 90, f"Agent in different collective should take damage, got hp={hp}"
