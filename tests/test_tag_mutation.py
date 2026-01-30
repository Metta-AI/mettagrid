"""Tests for AddTagMutation and RemoveTagMutation.

These tests verify that:
1. AddTagMutation correctly adds tags to entities in C++ simulation
2. RemoveTagMutation correctly removes tags from entities in C++ simulation
3. addTag() and removeTag() helper functions work correctly
"""

from mettagrid.config.filter import TagFilter
from mettagrid.config.filter.filter import HandlerTarget
from mettagrid.config.handler_config import AOEConfig
from mettagrid.config.mettagrid_config import (
    GridObjectConfig,
    MettaGridConfig,
    ResourceLimitsConfig,
)
from mettagrid.config.mutation import (
    AddTagMutation,
    AlignmentEntityTarget,
    EntityTarget,
    RemoveTagMutation,
    ResourceDeltaMutation,
    addTag,
    removeTag,
)
from mettagrid.config.tag import Tag
from mettagrid.simulator import Simulation


class TestAddTagMutation:
    """Test AddTagMutation adds tags correctly."""

    def test_add_tag_mutation_class(self):
        """AddTagMutation should have correct attributes."""
        m = AddTagMutation(tag=Tag("infected"), target=AlignmentEntityTarget.TARGET)
        assert m.mutation_type == "add_tag"
        assert m.tag == Tag("infected")
        assert m.target == AlignmentEntityTarget.TARGET


class TestRemoveTagMutation:
    """Test RemoveTagMutation removes tags correctly."""

    def test_remove_tag_mutation_class(self):
        """RemoveTagMutation should have correct attributes."""
        m = RemoveTagMutation(tag=Tag("infected"), target=AlignmentEntityTarget.TARGET)
        assert m.mutation_type == "remove_tag"
        assert m.tag == Tag("infected")
        assert m.target == AlignmentEntityTarget.TARGET


class TestTagMutationHelpers:
    """Test addTag() and removeTag() helper functions."""

    def test_add_tag_helper(self):
        """addTag() should create an AddTagMutation with the given tag."""
        m = addTag(Tag("infected"))
        assert isinstance(m, AddTagMutation)
        assert m.tag == Tag("infected")
        assert m.target == AlignmentEntityTarget.TARGET

    def test_add_tag_helper_with_target(self):
        """addTag() should accept target parameter."""
        m = addTag(Tag("buffed"), target=AlignmentEntityTarget.ACTOR)
        assert m.tag == Tag("buffed")
        assert m.target == AlignmentEntityTarget.ACTOR

    def test_remove_tag_helper(self):
        """removeTag() should create a RemoveTagMutation with the given tag."""
        m = removeTag(Tag("infected"))
        assert isinstance(m, RemoveTagMutation)
        assert m.tag == Tag("infected")
        assert m.target == AlignmentEntityTarget.TARGET

    def test_remove_tag_helper_with_target(self):
        """removeTag() should accept target parameter."""
        m = removeTag(Tag("buffed"), target=AlignmentEntityTarget.ACTOR)
        assert m.tag == Tag("buffed")
        assert m.target == AlignmentEntityTarget.ACTOR


class TestAddTagMutationEndToEnd:
    """End-to-end tests verifying AddTagMutation works in C++ simulation."""

    def test_aoe_add_tag_mutation_adds_tag_to_agent(self):
        """AOE handler with addTag mutation should add tag to agent in C++ simulation."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent
                ["#", ".", "S", ".", "#"],  # AOE source that adds "infected" tag
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "tagger"},
        )

        cfg.game.actions.noop.enabled = True

        # AOE source that adds "infected" tag to agents in range
        # Define "infected" tag on the source so it's registered in the tag map
        cfg.game.objects["tagger"] = GridObjectConfig(
            name="tagger",
            map_name="tagger",
            tags=[Tag("infected")],  # Register the tag so it's available for mutations
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[],
                    mutations=[addTag(Tag("infected"))],
                )
            },
        )

        sim = Simulation(cfg)

        # Get tag ID for "infected"
        id_map = cfg.game.id_map()
        tag_names = id_map.tag_names()
        tag_name_to_id = {name: idx for idx, name in enumerate(tag_names)}
        infected_id = tag_name_to_id["infected"]

        # Helper to check if agent has tag
        def agent_has_infected_tag():
            objects = sim._c_sim.grid_objects()
            for _obj_id, obj_data in objects.items():
                if obj_data["type_name"] == "agent":
                    return obj_data["has_tag"](infected_id)
            return False

        # Agent should NOT have infected tag initially
        assert not agent_has_infected_tag(), "Agent should not have 'infected' tag initially"

        # Step simulation - AOE should fire and add tag
        sim.agent(0).set_action("noop")
        sim.step()

        # Agent should now have infected tag
        assert agent_has_infected_tag(), "Agent should have 'infected' tag after AOE fired"

    def test_add_tag_enables_tag_filter(self):
        """After addTag mutation, TagFilter should match the entity."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent
                ["#", "T", "S", ".", "#"],  # T=tagger (adds tag), S=giver (gives energy to tagged)
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "T": "tagger", "S": "giver"},
        )

        cfg.game.resource_names = ["energy"]
        cfg.game.agent.inventory.initial = {"energy": 0}
        cfg.game.agent.inventory.limits = {
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
        }
        # No on_tick — no passive regen
        cfg.game.actions.noop.enabled = True

        # Tagger adds "blessed" tag
        # Define "blessed" tag on the tagger so it's registered in the tag map
        cfg.game.objects["tagger"] = GridObjectConfig(
            name="tagger",
            map_name="tagger",
            tags=[Tag("blessed")],  # Register the tag so it's available for mutations
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[],
                    mutations=[addTag(Tag("blessed"))],
                )
            },
        )

        # Giver only gives energy to agents with "blessed" tag
        cfg.game.objects["giver"] = GridObjectConfig(
            name="giver",
            map_name="giver",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[TagFilter(target=HandlerTarget.TARGET, tag=Tag("blessed"))],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 100})],
                )
            },
        )

        sim = Simulation(cfg)

        # Step once - tagger adds "blessed" tag, giver should then give energy
        sim.agent(0).set_action("noop")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        # The tag should be added and the giver should give energy in the same step
        # (AOE handlers fire in order, and the tag filter should see the newly added tag)
        assert energy == 100, f"Agent with 'blessed' tag should get energy, got {energy}"


class TestRemoveTagMutationEndToEnd:
    """End-to-end tests verifying RemoveTagMutation works in C++ simulation."""

    def test_aoe_remove_tag_mutation_removes_tag_from_agent(self):
        """AOE handler with removeTag mutation should remove tag from agent in C++ simulation."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent with "cursed" tag initially
                ["#", ".", "S", ".", "#"],  # AOE source that removes "cursed" tag
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "cleanser"},
        )

        # Agent starts with "cursed" tag
        cfg.game.agent.tags = [Tag("cursed")]
        cfg.game.actions.noop.enabled = True

        # AOE source that removes "cursed" tag from agents in range
        cfg.game.objects["cleanser"] = GridObjectConfig(
            name="cleanser",
            map_name="cleanser",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[],
                    mutations=[removeTag(Tag("cursed"))],
                )
            },
        )

        sim = Simulation(cfg)

        # Get tag ID for "cursed"
        id_map = cfg.game.id_map()
        tag_names = id_map.tag_names()
        tag_name_to_id = {name: idx for idx, name in enumerate(tag_names)}
        cursed_id = tag_name_to_id["cursed"]

        # Helper to check if agent has tag
        def agent_has_cursed_tag():
            objects = sim._c_sim.grid_objects()
            for _obj_id, obj_data in objects.items():
                if obj_data["type_name"] == "agent":
                    return obj_data["has_tag"](cursed_id)
            return False

        # Agent SHOULD have cursed tag initially
        assert agent_has_cursed_tag(), "Agent should have 'cursed' tag initially"

        # Step simulation - AOE should fire and remove tag
        sim.agent(0).set_action("noop")
        sim.step()

        # Agent should NOT have cursed tag anymore
        assert not agent_has_cursed_tag(), "Agent should not have 'cursed' tag after cleanse"

    def test_remove_tag_disables_tag_filter(self):
        """After removeTag mutation, TagFilter should no longer match the entity."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent with "vulnerable" tag
                ["#", "C", "D", ".", "#"],  # C=cleanser (removes tag), D=damager (damages vulnerable)
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "C": "cleanser", "D": "damager"},
        )

        cfg.game.resource_names = ["hp"]
        cfg.game.agent.tags = [Tag("vulnerable")]
        cfg.game.agent.inventory.initial = {"hp": 100}
        cfg.game.agent.inventory.limits = {
            "hp": ResourceLimitsConfig(min=1000, resources=["hp"]),
        }
        # No on_tick — no passive regen
        cfg.game.actions.noop.enabled = True

        # Cleanser removes "vulnerable" tag
        cfg.game.objects["cleanser"] = GridObjectConfig(
            name="cleanser",
            map_name="cleanser",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[],
                    mutations=[removeTag(Tag("vulnerable"))],
                )
            },
        )

        # Damager only damages agents with "vulnerable" tag
        cfg.game.objects["damager"] = GridObjectConfig(
            name="damager",
            map_name="damager",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[TagFilter(target=HandlerTarget.TARGET, tag=Tag("vulnerable"))],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"hp": -50})],
                )
            },
        )

        sim = Simulation(cfg)

        # Step once - cleanser removes tag, damager should NOT damage (tag already removed)
        sim.agent(0).set_action("noop")
        sim.step()

        hp = sim.agent(0).inventory.get("hp", 0)
        # If cleanser fires before damager, the tag is removed and damager shouldn't fire
        # This depends on handler execution order - test that at least one handler worked
        assert hp == 100, f"Agent without 'vulnerable' tag should not take damage, got hp={hp}"
