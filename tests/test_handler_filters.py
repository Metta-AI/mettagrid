"""Tests for handler filters (vibe, resource, alignment) on AOE handlers.

These tests verify that:
1. VibeFilter correctly gates handler execution based on entity vibe
2. AlignmentFilter correctly gates handler execution based on collective alignment
"""

from mettagrid.config.filter import (
    AlignmentFilter,
    MaxDistanceFilter,
    TagFilter,
    VibeFilter,
    anyOf,
    isNot,
    isNotAlignedTo,
    targetHas,
    targetHasAnyOf,
    targetVibe,
)
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
from mettagrid.config.query import Query
from mettagrid.config.tag import tag
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


class TestOrFilter:
    """Test OrFilter (anyOf) behavior on AOE handlers."""

    def test_or_filter_passes_when_first_filter_passes(self):
        """OrFilter should pass if the first inner filter passes."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent with junction vibe
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

        # AOE with anyOf([junction vibe, up vibe]) - should pass with junction
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[anyOf([targetVibe("junction"), targetVibe("up")])],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        # Set vibe to junction (first option in the OR)
        sim.agent(0).set_action("change_vibe_junction")
        sim.step()

        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy >= 10, f"OrFilter should pass when first filter matches, got {energy}"

    def test_or_filter_passes_when_second_filter_passes(self):
        """OrFilter should pass if the second inner filter passes."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent with up vibe
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

        # AOE with anyOf([junction vibe, up vibe]) - should pass with up
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[anyOf([targetVibe("junction"), targetVibe("up")])],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        # Set vibe to up (second option in the OR)
        sim.agent(0).set_action("change_vibe_up")
        sim.step()

        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy >= 10, f"OrFilter should pass when second filter matches, got {energy}"

    def test_or_filter_fails_when_no_filter_passes(self):
        """OrFilter should fail if no inner filter passes."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent with different vibe
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

        # AOE with anyOf([junction vibe, up vibe]) - should fail with down vibe
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[anyOf([targetVibe("junction"), targetVibe("up")])],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        # First verify default vibe doesn't match (it shouldn't based on first test)
        sim.agent(0).set_action("noop")
        sim.step()

        energy_default = sim.agent(0).inventory.get("energy", 0)
        assert energy_default == 0, f"Should not get energy with default vibe, got {energy_default}"

        # Set vibe to down (not junction or up)
        sim.agent(0).set_action("change_vibe_down")
        sim.step()

        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 0, f"OrFilter should fail when no filter matches, got {energy}"


class TestTargetHasAnyOf:
    """Test targetHasAnyOf helper function."""

    def test_target_has_any_of_passes_with_first_resource(self):
        """targetHasAnyOf should pass if target has the first resource."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent with gold
                ["#", ".", "S", ".", "#"],  # AOE source
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "aoe_source"},
        )

        cfg.game.resource_names = ["gold", "silver", "energy"]
        cfg.game.agent.inventory.initial = {"gold": 5, "silver": 0, "energy": 0}
        cfg.game.agent.inventory.limits = {
            "gold": ResourceLimitsConfig(min=1000, resources=["gold"]),
            "silver": ResourceLimitsConfig(min=1000, resources=["silver"]),
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
        }
        cfg.game.actions.noop.enabled = True

        # AOE with targetHasAnyOf(["gold", "silver"]) - should pass when target (agent) has gold
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[targetHasAnyOf(["gold", "silver"])],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, f"targetHasAnyOf should pass when target has first resource, got {energy}"

    def test_target_has_any_of_passes_with_second_resource(self):
        """targetHasAnyOf should pass if target has the second resource."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent with silver
                ["#", ".", "S", ".", "#"],  # AOE source
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "aoe_source"},
        )

        cfg.game.resource_names = ["gold", "silver", "energy"]
        cfg.game.agent.inventory.initial = {"gold": 0, "silver": 5, "energy": 0}
        cfg.game.agent.inventory.limits = {
            "gold": ResourceLimitsConfig(min=1000, resources=["gold"]),
            "silver": ResourceLimitsConfig(min=1000, resources=["silver"]),
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
        }
        cfg.game.actions.noop.enabled = True

        # AOE with targetHasAnyOf(["gold", "silver"]) - should pass when target (agent) has silver
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[targetHasAnyOf(["gold", "silver"])],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, f"targetHasAnyOf should pass when target has second resource, got {energy}"

    def test_target_has_any_of_fails_with_no_resources(self):
        """targetHasAnyOf should fail if target has none of the resources."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent with no gold or silver
                ["#", ".", "S", ".", "#"],  # AOE source
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "aoe_source"},
        )

        cfg.game.resource_names = ["gold", "silver", "energy"]
        cfg.game.agent.inventory.initial = {"gold": 0, "silver": 0, "energy": 0}
        cfg.game.agent.inventory.limits = {
            "gold": ResourceLimitsConfig(min=1000, resources=["gold"]),
            "silver": ResourceLimitsConfig(min=1000, resources=["silver"]),
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
        }
        cfg.game.actions.noop.enabled = True

        # AOE with targetHasAnyOf(["gold", "silver"]) - should fail when target has neither
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[targetHasAnyOf(["gold", "silver"])],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 0, f"targetHasAnyOf should fail when target has no matching resources, got {energy}"


class TestOrFilterMultiResourceAndSemantics:
    """Test that multi-resource filters inside OrFilter preserve AND semantics.

    When a ResourceFilter with multiple resources (e.g., {"gold": 1, "silver": 1}) is used
    inside an OrFilter, it should require ALL resources (AND semantics), not just any one.

    This verifies the fix for: "Preserve multi-resource AND when wrapping in OrFilter"
    """

    def test_or_filter_multi_resource_requires_all_resources(self):
        """OrFilter with multi-resource filter should require ALL resources to pass."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent with only gold (not silver)
                ["#", ".", "S", ".", "#"],  # AOE source
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "aoe_source"},
        )

        cfg.game.resource_names = ["gold", "silver", "bronze", "energy"]
        cfg.game.agent.inventory.initial = {"gold": 5, "silver": 0, "bronze": 0, "energy": 0}
        cfg.game.agent.inventory.limits = {
            "gold": ResourceLimitsConfig(min=1000, resources=["gold"]),
            "silver": ResourceLimitsConfig(min=1000, resources=["silver"]),
            "bronze": ResourceLimitsConfig(min=1000, resources=["bronze"]),
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
        }
        cfg.game.actions.noop.enabled = True

        # AOE with anyOf([targetHas({"gold": 1, "silver": 1}), targetHas({"bronze": 1})])
        # First branch requires BOTH gold AND silver
        # Second branch requires bronze
        # Agent has gold but not silver, and no bronze - should NOT pass
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[anyOf([targetHas({"gold": 1, "silver": 1}), targetHas({"bronze": 1})])],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 0, (
            f"Agent with only gold (not silver or bronze) should NOT pass OrFilter. "
            f"Multi-resource filter should require ALL resources, got energy={energy}"
        )

    def test_or_filter_multi_resource_passes_when_all_present(self):
        """OrFilter with multi-resource filter should pass when ALL resources are present."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent with both gold AND silver
                ["#", ".", "S", ".", "#"],  # AOE source
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "aoe_source"},
        )

        cfg.game.resource_names = ["gold", "silver", "bronze", "energy"]
        cfg.game.agent.inventory.initial = {"gold": 5, "silver": 3, "bronze": 0, "energy": 0}
        cfg.game.agent.inventory.limits = {
            "gold": ResourceLimitsConfig(min=1000, resources=["gold"]),
            "silver": ResourceLimitsConfig(min=1000, resources=["silver"]),
            "bronze": ResourceLimitsConfig(min=1000, resources=["bronze"]),
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
        }
        cfg.game.actions.noop.enabled = True

        # AOE with anyOf([targetHas({"gold": 1, "silver": 1}), targetHas({"bronze": 1})])
        # First branch requires BOTH gold AND silver
        # Agent has both gold and silver - should pass via first branch
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[anyOf([targetHas({"gold": 1, "silver": 1}), targetHas({"bronze": 1})])],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, (
            f"Agent with both gold AND silver should pass OrFilter via multi-resource branch, got energy={energy}"
        )

    def test_or_filter_multi_resource_second_branch_fallback(self):
        """OrFilter should pass via second branch if first multi-resource branch fails."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent with bronze only
                ["#", ".", "S", ".", "#"],  # AOE source
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "aoe_source"},
        )

        cfg.game.resource_names = ["gold", "silver", "bronze", "energy"]
        cfg.game.agent.inventory.initial = {"gold": 0, "silver": 0, "bronze": 5, "energy": 0}
        cfg.game.agent.inventory.limits = {
            "gold": ResourceLimitsConfig(min=1000, resources=["gold"]),
            "silver": ResourceLimitsConfig(min=1000, resources=["silver"]),
            "bronze": ResourceLimitsConfig(min=1000, resources=["bronze"]),
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
        }
        cfg.game.actions.noop.enabled = True

        # AOE with anyOf([targetHas({"gold": 1, "silver": 1}), targetHas({"bronze": 1})])
        # First branch requires BOTH gold AND silver (agent lacks both)
        # Second branch requires bronze (agent has it) - should pass via second branch
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[anyOf([targetHas({"gold": 1, "silver": 1}), targetHas({"bronze": 1})])],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, f"Agent with bronze should pass OrFilter via second branch, got energy={energy}"


class TestCollectiveAlignmentFilter:
    """Test alignment filter with specific collective targeting.

    These tests verify that alignment filters with the 'collective' attribute work
    correctly across all filter contexts: handlers, events, near filters, and AOE filters.
    """

    def test_handler_alignment_filter_with_collective(self):
        """Handler alignment filter with collective should filter by specific collective."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent (cogs collective)
                ["#", ".", "S", ".", "#"],  # Object with on_tick handler
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "source"},
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
            "clips": CollectiveConfig(
                inventory=InventoryConfig(limits={"energy": ResourceLimitsConfig(min=10000, resources=["energy"])})
            ),
        }

        # Object with AOE that uses alignment filter with specific collective
        # This tests that _convert_filters handles collective on alignment filters
        cfg.game.objects["source"] = GridObjectConfig(
            name="source",
            map_name="source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[
                        AlignmentFilter(
                            target=HandlerTarget.TARGET,
                            alignment=AlignmentCondition.ALIGNED,
                            collective="cogs",  # Only affects agents aligned to cogs
                        )
                    ],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        # Agent is in cogs, filter checks for alignment to cogs - should pass
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, f"Agent in cogs should receive energy with collective alignment filter, got {energy}"

    def test_handler_alignment_filter_with_different_collective_blocks(self):
        """Handler alignment filter with different collective should block non-matching agents."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent (cogs collective)
                ["#", ".", "S", ".", "#"],  # Object with AOE
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "source"},
        )

        cfg.game.resource_names = ["energy"]
        cfg.game.agent.collective = "cogs"  # Agent in cogs
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

        # Object with AOE that uses alignment filter for clips collective
        cfg.game.objects["source"] = GridObjectConfig(
            name="source",
            map_name="source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[
                        AlignmentFilter(
                            target=HandlerTarget.TARGET,
                            alignment=AlignmentCondition.ALIGNED,
                            collective="clips",  # Only affects agents aligned to clips
                        )
                    ],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        # Agent is in cogs, filter checks for clips - should NOT pass
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 0, f"Agent in cogs should NOT receive energy with clips filter, got {energy}"

    def test_near_filter_with_collective_alignment(self):
        """Near filter containing alignment filter with collective should convert without error.

        Note: This test verifies the filter conversion works. Testing the runtime behavior
        of nested near+alignment filters would require a more complex scenario with multiple
        agents, which is beyond the scope of this refactoring test.
        """
        # This test verifies that the unified _convert_filters correctly passes
        # collective_name_to_id to nested near filter conversions.
        # The actual runtime test is complex due to near filter semantics.

        # Import to verify the config can be built without errors

        cfg = MettaGridConfig.EmptyRoom(num_agents=2, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "0", "1", "#"],  # Two agents from same collective
                ["#", ".", "S", ".", "#"],  # AOE source
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "0": "agent.agent", "1": "agent.agent", ".": "empty", "S": "aoe_source"},
        )

        cfg.game.resource_names = ["energy"]
        cfg.game.agent.collective = "cogs"
        cfg.game.agent.inventory.initial = {"energy": 0}
        cfg.game.agent.inventory.limits = {
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
        }
        cfg.game.tags = [tag("near_target")]
        cfg.game.agent.tags = ["near_target"]
        cfg.game.actions.noop.enabled = True

        cfg.game.collectives = {
            "cogs": CollectiveConfig(
                inventory=InventoryConfig(limits={"energy": ResourceLimitsConfig(min=10000, resources=["energy"])})
            ),
        }

        # AOE with near filter that has alignment filter with collective inside
        # The agent (target) must be near another entity with the "near_target" tag
        # AND that nearby entity must be aligned to "cogs" collective
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=3,
                    filters=[
                        MaxDistanceFilter(
                            target=HandlerTarget.TARGET,
                            radius=2,
                            query=Query(
                                source="near_target",
                                filters=[
                                    TagFilter(
                                        target=HandlerTarget.TARGET,
                                        tag=tag("collective:cogs"),
                                    )
                                ],
                            ),
                        )
                    ],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        # Just verify the simulation can be created without errors
        # (this validates the filter conversion works)
        sim = Simulation(cfg)

        # Run one step to make sure no crash occurs
        sim.agent(0).set_action("noop")
        sim.agent(1).set_action("noop")
        sim.step()

        # Test passes if we get here without a crash
        # The actual filter behavior depends on C++ implementation details

    def test_or_filter_with_collective_alignment(self):
        """Or filter containing alignment filter with collective should work correctly."""
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
            "clips": CollectiveConfig(
                inventory=InventoryConfig(limits={"energy": ResourceLimitsConfig(min=10000, resources=["energy"])})
            ),
        }

        # AOE with anyOf filter containing collective alignment filters
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[
                        anyOf(
                            [
                                AlignmentFilter(
                                    target=HandlerTarget.TARGET,
                                    alignment=AlignmentCondition.ALIGNED,
                                    collective="clips",  # First branch - clips (won't match)
                                ),
                                AlignmentFilter(
                                    target=HandlerTarget.TARGET,
                                    alignment=AlignmentCondition.ALIGNED,
                                    collective="cogs",  # Second branch - cogs (will match)
                                ),
                            ]
                        )
                    ],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, f"OrFilter with collective alignment should pass via second branch, got {energy}"

    def test_not_filter_with_collective_alignment(self):
        """Not filter wrapping alignment filter with collective should work correctly."""
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
            "clips": CollectiveConfig(
                inventory=InventoryConfig(limits={"energy": ResourceLimitsConfig(min=10000, resources=["energy"])})
            ),
        }

        # AOE with isNot(aligned to clips) - agent is in cogs, so NOT clips should pass
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[
                        isNot(
                            AlignmentFilter(
                                target=HandlerTarget.TARGET,
                                alignment=AlignmentCondition.ALIGNED,
                                collective="clips",  # NOT aligned to clips
                            )
                        )
                    ],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, f"isNot(aligned to clips) should pass for cogs agent, got {energy}"


class TestNestedOrFilter:
    """Test nested OrFilter conversion.

    This verifies that OrFilters can be nested within other OrFilters.
    """

    def test_nested_or_filter_passes_via_outer_branch(self):
        """Nested OrFilter should work when outer branch passes."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent with gold
                ["#", ".", "S", ".", "#"],  # AOE source
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "aoe_source"},
        )

        cfg.game.resource_names = ["gold", "silver", "bronze", "energy"]
        cfg.game.agent.inventory.initial = {"gold": 5, "silver": 0, "bronze": 0, "energy": 0}
        cfg.game.agent.inventory.limits = {
            "gold": ResourceLimitsConfig(min=1000, resources=["gold"]),
            "silver": ResourceLimitsConfig(min=1000, resources=["silver"]),
            "bronze": ResourceLimitsConfig(min=1000, resources=["bronze"]),
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
        }
        cfg.game.actions.noop.enabled = True

        # Nested OrFilter: anyOf([targetHas({"gold": 1}), anyOf([targetHas({"silver": 1}), targetHas({"bronze": 1})])])
        # Outer OR: gold OR (silver OR bronze)
        # Agent has gold - should pass via first outer branch
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[
                        anyOf(
                            [
                                targetHas({"gold": 1}),
                                anyOf([targetHas({"silver": 1}), targetHas({"bronze": 1})]),
                            ]
                        )
                    ],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, f"Nested OrFilter should pass via outer gold branch, got energy={energy}"

    def test_nested_or_filter_passes_via_inner_first_branch(self):
        """Nested OrFilter should work when inner first branch passes."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent with silver
                ["#", ".", "S", ".", "#"],  # AOE source
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "aoe_source"},
        )

        cfg.game.resource_names = ["gold", "silver", "bronze", "energy"]
        cfg.game.agent.inventory.initial = {"gold": 0, "silver": 5, "bronze": 0, "energy": 0}
        cfg.game.agent.inventory.limits = {
            "gold": ResourceLimitsConfig(min=1000, resources=["gold"]),
            "silver": ResourceLimitsConfig(min=1000, resources=["silver"]),
            "bronze": ResourceLimitsConfig(min=1000, resources=["bronze"]),
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
        }
        cfg.game.actions.noop.enabled = True

        # Nested OrFilter: anyOf([targetHas({"gold": 1}), anyOf([targetHas({"silver": 1}), targetHas({"bronze": 1})])])
        # Outer OR: gold OR (silver OR bronze)
        # Agent has silver - should pass via nested OR's first branch
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[
                        anyOf(
                            [
                                targetHas({"gold": 1}),
                                anyOf([targetHas({"silver": 1}), targetHas({"bronze": 1})]),
                            ]
                        )
                    ],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, f"Nested OrFilter should pass via inner silver branch, got energy={energy}"

    def test_nested_or_filter_passes_via_inner_second_branch(self):
        """Nested OrFilter should work when inner second branch passes."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent with bronze
                ["#", ".", "S", ".", "#"],  # AOE source
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "aoe_source"},
        )

        cfg.game.resource_names = ["gold", "silver", "bronze", "energy"]
        cfg.game.agent.inventory.initial = {"gold": 0, "silver": 0, "bronze": 5, "energy": 0}
        cfg.game.agent.inventory.limits = {
            "gold": ResourceLimitsConfig(min=1000, resources=["gold"]),
            "silver": ResourceLimitsConfig(min=1000, resources=["silver"]),
            "bronze": ResourceLimitsConfig(min=1000, resources=["bronze"]),
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
        }
        cfg.game.actions.noop.enabled = True

        # Nested OrFilter: anyOf([targetHas({"gold": 1}), anyOf([targetHas({"silver": 1}), targetHas({"bronze": 1})])])
        # Outer OR: gold OR (silver OR bronze)
        # Agent has bronze - should pass via nested OR's second branch
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[
                        anyOf(
                            [
                                targetHas({"gold": 1}),
                                anyOf([targetHas({"silver": 1}), targetHas({"bronze": 1})]),
                            ]
                        )
                    ],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, f"Nested OrFilter should pass via inner bronze branch, got energy={energy}"

    def test_nested_or_filter_fails_when_no_branch_passes(self):
        """Nested OrFilter should fail when no branch passes."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent with no matching resources
                ["#", ".", "S", ".", "#"],  # AOE source
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "aoe_source"},
        )

        cfg.game.resource_names = ["gold", "silver", "bronze", "energy"]
        cfg.game.agent.inventory.initial = {"gold": 0, "silver": 0, "bronze": 0, "energy": 0}
        cfg.game.agent.inventory.limits = {
            "gold": ResourceLimitsConfig(min=1000, resources=["gold"]),
            "silver": ResourceLimitsConfig(min=1000, resources=["silver"]),
            "bronze": ResourceLimitsConfig(min=1000, resources=["bronze"]),
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
        }
        cfg.game.actions.noop.enabled = True

        # Nested OrFilter: anyOf([targetHas({"gold": 1}), anyOf([targetHas({"silver": 1}), targetHas({"bronze": 1})])])
        # Agent has none of the resources - should fail
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[
                        anyOf(
                            [
                                targetHas({"gold": 1}),
                                anyOf([targetHas({"silver": 1}), targetHas({"bronze": 1})]),
                            ]
                        )
                    ],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 0, f"Nested OrFilter should fail when no resources match, got energy={energy}"
