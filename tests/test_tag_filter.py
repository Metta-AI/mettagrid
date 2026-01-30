"""Tests for TagFilter on handlers.

These tests verify that:
1. TagFilter correctly gates handler execution based on entity tags
2. hasTag() and isA() helper functions work correctly
"""

from mettagrid.config.filter import HandlerTarget, TagFilter, hasTag, isA
from mettagrid.config.handler_config import AOEConfig
from mettagrid.config.mettagrid_config import (
    GridObjectConfig,
    MettaGridConfig,
    ResourceLimitsConfig,
)
from mettagrid.config.mutation import EntityTarget, ResourceDeltaMutation
from mettagrid.config.tag import Tag, typeTag
from mettagrid.simulator import Simulation


class TestTagFilter:
    """Test tag filter on AOE handlers."""

    def test_tag_filter_only_affects_matching_objects(self):
        """AOE handler with tag filter should only affect entities with matching tag."""
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

        # Add tags to agent (type:agent is auto-generated from agent name)
        cfg.game.agent.tags = [Tag("mobile")]

        # AOE source with tag filter - only affects objects with "type:agent" tag (auto-generated)
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[TagFilter(target=HandlerTarget.TARGET, tag=typeTag("agent"))],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        # Step - agent has type:agent tag (auto-generated), should get energy
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, f"Agent with matching tag should get energy, got {energy}"

    def test_tag_filter_blocks_non_matching_objects(self):
        """AOE handler with tag filter should NOT affect entities without matching tag."""
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

        # Agent has "mobile" tag but not "type:structure"
        cfg.game.agent.tags = [Tag("mobile")]

        # Add a structure object so type:structure is auto-registered as a tag
        cfg.game.objects["structure"] = GridObjectConfig(name="structure", map_name="structure")

        # AOE source with tag filter - only affects objects with "type:structure" tag (auto-generated)
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[TagFilter(target=HandlerTarget.TARGET, tag=typeTag("structure"))],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        # Step - agent does NOT have type:structure tag, should NOT get energy
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 0, f"Agent without matching tag should NOT get energy, got {energy}"


class TestTagFilterHelpers:
    """Test hasTag() and isA() helper functions."""

    def test_has_tag_helper(self):
        """hasTag() should create a TagFilter with the given tag."""
        f = hasTag(Tag("type:junction"))
        assert isinstance(f, TagFilter)
        assert f.tag == Tag("type:junction")

    def test_is_a_helper(self):
        """isA() should create a TagFilter with type:value format."""
        f = isA("hub")
        assert isinstance(f, TagFilter)
        assert f.tag == Tag("type:hub")

    def test_is_a_helper_with_junction(self):
        """isA() should work with junction type."""
        f = isA("junction")
        assert f.tag == Tag("type:junction")
