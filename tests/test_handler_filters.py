"""Tests for handler filters (vibe, resource, alignment) on AOE handlers.

These tests verify that:
1. VibeFilter correctly gates handler execution based on entity vibe
2. AlignmentFilter correctly gates handler execution based on collective alignment
"""

from mettagrid.config.filter import AlignmentFilter, VibeFilter, isNot, isNotAlignedTo, targetHas, targetVibe
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

        # AOE source with vibe filter - only affects agents with "junction" vibe
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[targetVibe("junction")],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        # Step without junction vibe - should NOT get energy
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 0, f"Should NOT get energy without junction vibe, got {energy}"

        # Change vibe to junction - AOE fires at end of this step too (agent now has junction vibe)
        sim.agent(0).set_action("change_vibe_junction")
        sim.step()

        # After changing vibe, the AOE should have fired once (during change_vibe step)
        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, f"Should get energy after changing to junction vibe, got {energy}"

        # Step with junction vibe - should get more energy
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 20, f"Should have 20 energy after second step with junction vibe, got {energy}"

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

        # AOE source that requires "junction" vibe
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[targetVibe("junction")],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        # Change to "up" vibe (not junction)
        sim.agent(0).set_action("change_vibe_up")
        sim.step()

        # Step with "up" vibe - should NOT get energy (filter requires "junction")
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


class TestNotFilterOnAOE:
    """Test NotFilter (isNot) behavior on AOE handlers."""

    def test_aoe_not_alignment_filter_same_collective(self):
        """AOE with isNot(same_collective) filter should only affect non-aligned agents."""
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
        cfg.game.actions.noop.enabled = True

        # Define collectives
        cfg.game.collectives = {
            "cogs": CollectiveConfig(
                inventory=InventoryConfig(limits={"energy": ResourceLimitsConfig(min=10000, resources=["energy"])})
            ),
        }

        # AOE source with isNot(same_collective) filter - only affects NON-aligned agents
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            collective="cogs",  # Same collective as agent
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[
                        isNot(
                            AlignmentFilter(
                                target=HandlerTarget.TARGET,
                                alignment=AlignmentCondition.SAME_COLLECTIVE,
                            )
                        )  # passes if NOT same collective
                    ],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        # Step - agent and AOE source are in same collective, but filter is negated
        # So the filter should FAIL and agent should NOT receive energy
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 0, f"Agent in same collective should NOT receive energy with isNot filter, got {energy}"

    def test_aoe_not_alignment_filter_different_collective(self):
        """AOE with isNot(same_collective) filter should affect agents in different collective."""
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

        # AOE source with isNot(same_collective) filter - affects NON-aligned agents
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            collective="clips",  # Different collective from agent
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[
                        isNot(
                            AlignmentFilter(
                                target=HandlerTarget.TARGET,
                                alignment=AlignmentCondition.SAME_COLLECTIVE,
                            )
                        )  # passes if NOT same collective
                    ],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        # Step - agent is cogs, AOE source is clips, filter is negated
        # So the filter should PASS and agent should receive energy
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, f"Agent in different collective should receive energy with isNot filter, got {energy}"

    def test_aoe_not_vibe_filter(self):
        """AOE with isNot(vibe) filter should affect agents WITHOUT the specified vibe."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent (default vibe)
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
        cfg.game.actions.noop.enabled = True

        # AOE source with isNot(vibe) filter - affects agents WITHOUT "junction" vibe
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[
                        isNot(
                            VibeFilter(
                                target=HandlerTarget.TARGET,
                                vibe="junction",
                            )
                        )  # passes if NOT junction vibe
                    ],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        # Step without junction vibe - negated filter should PASS
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, f"Agent without junction vibe should receive energy with isNot filter, got {energy}"

        # Change vibe to junction - negated filter should now FAIL
        sim.agent(0).set_action("change_vibe_junction")
        sim.step()

        # Step with junction vibe - negated filter should FAIL
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        # 10 from first step only. Steps 2 and 3 should not add energy because the vibe
        # changed to junction during step 2, and the negated filter blocks junction vibe.
        assert energy == 10, (
            f"Agent with junction vibe should NOT receive additional energy with isNot filter, got {energy}"
        )


class TestIsNotAlignedToHelper:
    """Test the isNotAlignedTo helper function."""

    def test_is_not_aligned_to_collective(self):
        """isNotAlignedTo should filter out agents that ARE in the specified collective."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent (cogs collective)
                ["#", ".", "S", ".", "#"],  # AOE source
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "aoe_source"},
        )

        cfg.game.resource_names = ["energy"]
        cfg.game.agent.collective = "cogs"
        cfg.game.agent.inventory.initial = {"energy": 0}
        cfg.game.agent.inventory.limits = {
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
        }
        cfg.game.actions.noop.enabled = True

        cfg.game.collectives = {
            "cogs": CollectiveConfig(
                inventory=InventoryConfig(limits={"energy": ResourceLimitsConfig(min=10000, resources=["energy"])})
            ),
        }

        # AOE with isNotAlignedTo("cogs") - should NOT affect cogs agents
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[isNotAlignedTo("cogs")],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        # Agent is in cogs, filter is isNotAlignedTo("cogs"), so agent should NOT receive energy
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 0, f"Agent in cogs should NOT receive energy with isNotAlignedTo('cogs'), got {energy}"

    def test_is_not_aligned_to_different_collective(self):
        """isNotAlignedTo should allow agents NOT in the specified collective."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent (clips collective)
                ["#", ".", "S", ".", "#"],  # AOE source
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "aoe_source"},
        )

        cfg.game.resource_names = ["energy"]
        cfg.game.agent.collective = "clips"  # Agent in different collective
        cfg.game.agent.inventory.initial = {"energy": 0}
        cfg.game.agent.inventory.limits = {
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
        }
        cfg.game.actions.noop.enabled = True

        cfg.game.collectives = {
            "cogs": CollectiveConfig(
                inventory=InventoryConfig(limits={"energy": ResourceLimitsConfig(min=10000, resources=["energy"])})
            ),
            "clips": CollectiveConfig(
                inventory=InventoryConfig(limits={"energy": ResourceLimitsConfig(min=10000, resources=["energy"])})
            ),
        }

        # AOE with isNotAlignedTo("cogs") - should affect non-cogs agents
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[isNotAlignedTo("cogs")],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        # Agent is in clips, filter is isNotAlignedTo("cogs"), so agent SHOULD receive energy
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, f"Agent in clips should receive energy with isNotAlignedTo('cogs'), got {energy}"


class TestMultiResourceNegatedFilter:
    """Test that isNot(targetHas({...multiple resources...})) has correct NOT(A AND B) semantics.

    When negating a multi-resource filter, the semantics should be:
    - NOT (has gold >= 1 AND has key >= 1)
    - Which is equivalent to: (lacks gold) OR (lacks key)
    - The filter should PASS if the target is missing ANY of the required resources

    Previously, this was incorrectly implemented as:
    - (NOT gold >= 1) AND (NOT key >= 1)
    - Which meant the target had to lack ALL resources for the filter to pass
    """

    def test_negated_multi_resource_filter_passes_when_missing_one(self):
        """Negated multi-resource filter should pass if target lacks ANY required resource."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent (has gold, but NOT key)
                ["#", ".", "S", ".", "#"],  # AOE source
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "aoe_source"},
        )

        cfg.game.resource_names = ["gold", "key", "energy"]
        cfg.game.agent.inventory.initial = {"gold": 5, "key": 0, "energy": 0}  # Has gold, lacks key
        cfg.game.agent.inventory.limits = {
            "gold": ResourceLimitsConfig(min=1000, resources=["gold"]),
            "key": ResourceLimitsConfig(min=1000, resources=["key"]),
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
        }
        cfg.game.actions.noop.enabled = True

        # AOE with isNot(targetHas({"gold": 1, "key": 1}))
        # Should pass if target lacks gold OR key (i.e., NOT (gold >= 1 AND key >= 1))
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[isNot(targetHas({"gold": 1, "key": 1}))],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        # Agent has gold but lacks key - negated filter should PASS
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, (
            f"Agent lacking one of the required resources should receive energy (filter should pass), got {energy}"
        )

    def test_negated_multi_resource_filter_fails_when_has_all(self):
        """Negated multi-resource filter should fail if target has ALL required resources."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent (has both gold AND key)
                ["#", ".", "S", ".", "#"],  # AOE source
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "aoe_source"},
        )

        cfg.game.resource_names = ["gold", "key", "energy"]
        cfg.game.agent.inventory.initial = {"gold": 5, "key": 3, "energy": 0}  # Has both gold and key
        cfg.game.agent.inventory.limits = {
            "gold": ResourceLimitsConfig(min=1000, resources=["gold"]),
            "key": ResourceLimitsConfig(min=1000, resources=["key"]),
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
        }
        cfg.game.actions.noop.enabled = True

        # AOE with isNot(targetHas({"gold": 1, "key": 1}))
        # Should fail if target has BOTH gold AND key
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[isNot(targetHas({"gold": 1, "key": 1}))],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        # Agent has both gold and key - negated filter should FAIL
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 0, (
            f"Agent with all required resources should NOT receive energy (filter should fail), got {energy}"
        )

    def test_negated_multi_resource_filter_passes_when_missing_all(self):
        """Negated multi-resource filter should pass if target lacks ALL required resources."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent (has neither gold nor key)
                ["#", ".", "S", ".", "#"],  # AOE source
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "aoe_source"},
        )

        cfg.game.resource_names = ["gold", "key", "energy"]
        cfg.game.agent.inventory.initial = {"gold": 0, "key": 0, "energy": 0}  # Has neither gold nor key
        cfg.game.agent.inventory.limits = {
            "gold": ResourceLimitsConfig(min=1000, resources=["gold"]),
            "key": ResourceLimitsConfig(min=1000, resources=["key"]),
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
        }
        cfg.game.actions.noop.enabled = True

        # AOE with isNot(targetHas({"gold": 1, "key": 1}))
        # Should pass if target lacks gold OR key (and definitely passes if lacks both)
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[isNot(targetHas({"gold": 1, "key": 1}))],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        # Agent lacks both gold and key - negated filter should PASS
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, (
            f"Agent lacking all required resources should receive energy (filter should pass), got {energy}"
        )
