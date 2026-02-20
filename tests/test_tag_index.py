"""Tests for TagIndex class."""

from mettagrid.config.handler_config import AOEConfig, Handler
from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    AgentConfig,
    GameConfig,
    GridObjectConfig,
    MettaGridConfig,
    NoopActionConfig,
    ObsConfig,
    ResourceLimitsConfig,
    WallConfig,
)
from mettagrid.config.mutation import (
    EntityTarget,
    ResourceDeltaMutation,
    addTag,
    removeTag,
)
from mettagrid.map_builder.ascii import AsciiMapBuilder
from mettagrid.mapgen.utils.ascii_grid import DEFAULT_CHAR_TO_NAME
from mettagrid.mettagrid_c import TagIndex
from mettagrid.simulator import Simulation


class TestTagIndex:
    def test_tag_index_exists(self):
        """TagIndex class should be importable."""
        index = TagIndex()
        assert index is not None


class TestGridObjectTagMethods:
    """Tests for GridObject has_tag, add_tag, remove_tag methods."""

    def test_grid_object_has_tag(self):
        """GridObject should have has_tag method that returns correct values."""
        cfg = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=5, height=5, num_tokens=100),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                objects={"wall": WallConfig(tags=["solid", "blocking"])},
                agents=[AgentConfig(tags=["mobile", "player"])],
                resource_names=[],
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        ["#", "#", "#", "#", "#"],
                        ["#", "@", ".", ".", "#"],
                        ["#", ".", ".", ".", "#"],
                        ["#", ".", ".", ".", "#"],
                        ["#", "#", "#", "#", "#"],
                    ],
                    char_to_map_name=DEFAULT_CHAR_TO_NAME,
                ),
            )
        )
        sim = Simulation(cfg)

        # Get tag ID mapping from the config
        id_map = cfg.game.id_map()
        tag_names = id_map.tag_names()
        tag_name_to_id = {name: idx for idx, name in enumerate(tag_names)}

        # Get the agent (first object after walls typically)
        objects = sim._c_sim.grid_objects()

        # Find an agent object
        agent_obj = None
        for _obj_id, obj_data in objects.items():
            if obj_data["type_name"] == "agent":
                agent_obj = obj_data
                break

        assert agent_obj is not None, "Should find an agent object"

        # Agent should have "mobile" and "player" tags
        mobile_id = tag_name_to_id["mobile"]
        player_id = tag_name_to_id["player"]
        blocking_id = tag_name_to_id["blocking"]
        solid_id = tag_name_to_id["solid"]

        assert agent_obj["has_tag"](mobile_id) is True, "Agent should have 'mobile' tag"
        assert agent_obj["has_tag"](player_id) is True, "Agent should have 'player' tag"
        assert agent_obj["has_tag"](blocking_id) is False, "Agent should not have 'blocking' tag"
        assert agent_obj["has_tag"](solid_id) is False, "Agent should not have 'solid' tag"

    def test_grid_object_add_tag(self):
        """GridObject add_tag should add a tag."""
        cfg = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=3, height=3, num_tokens=100),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                objects={"wall": WallConfig(tags=["solid"])},
                agents=[AgentConfig(tags=["mobile"])],
                resource_names=[],
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        ["#", "#", "#"],
                        ["#", "@", "#"],
                        ["#", "#", "#"],
                    ],
                    char_to_map_name=DEFAULT_CHAR_TO_NAME,
                ),
            )
        )
        sim = Simulation(cfg)

        # Get tag ID mapping from the config
        id_map = cfg.game.id_map()
        tag_names = id_map.tag_names()
        tag_name_to_id = {name: idx for idx, name in enumerate(tag_names)}
        mobile_id = tag_name_to_id["mobile"]
        solid_id = tag_name_to_id["solid"]

        objects = sim._c_sim.grid_objects()

        # Find the agent
        agent_obj = None
        for _obj_id, obj_data in objects.items():
            if obj_data["type_name"] == "agent":
                agent_obj = obj_data
                break

        assert agent_obj is not None

        # Agent has mobile, not solid
        assert agent_obj["has_tag"](mobile_id) is True, "Agent should have 'mobile' tag"
        assert agent_obj["has_tag"](solid_id) is False, "Agent should not have 'solid' tag yet"

        # Add 'solid' tag
        agent_obj["add_tag"](solid_id)

        # Now agent should have both tags
        assert agent_obj["has_tag"](solid_id) is True, "Agent should now have 'solid' tag"

    def test_grid_object_remove_tag(self):
        """GridObject remove_tag should remove a tag."""
        cfg = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=3, height=3, num_tokens=100),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                objects={"wall": WallConfig(tags=["solid"])},
                agents=[AgentConfig(tags=["mobile", "player"])],
                resource_names=[],
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        ["#", "#", "#"],
                        ["#", "@", "#"],
                        ["#", "#", "#"],
                    ],
                    char_to_map_name=DEFAULT_CHAR_TO_NAME,
                ),
            )
        )
        sim = Simulation(cfg)

        # Get tag ID mapping from the config
        id_map = cfg.game.id_map()
        tag_names = id_map.tag_names()
        tag_name_to_id = {name: idx for idx, name in enumerate(tag_names)}
        mobile_id = tag_name_to_id["mobile"]
        player_id = tag_name_to_id["player"]

        objects = sim._c_sim.grid_objects()

        # Find the agent
        agent_obj = None
        for _obj_id, obj_data in objects.items():
            if obj_data["type_name"] == "agent":
                agent_obj = obj_data
                break

        assert agent_obj is not None

        assert agent_obj["has_tag"](mobile_id) is True, "Agent should have 'mobile' tag"
        assert agent_obj["has_tag"](player_id) is True, "Agent should have 'player' tag"

        # Remove 'mobile' tag
        agent_obj["remove_tag"](mobile_id)

        # Now agent should only have 'player' tag
        assert agent_obj["has_tag"](mobile_id) is False, "Agent should no longer have 'mobile' tag"
        assert agent_obj["has_tag"](player_id) is True, "Agent should still have 'player' tag"

    def test_add_tag_idempotent(self):
        """Adding a tag that already exists should be a no-op."""
        cfg = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=3, height=3, num_tokens=100),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                agents=[AgentConfig(tags=["mobile"])],
                resource_names=[],
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        [".", ".", "."],
                        [".", "@", "."],
                        [".", ".", "."],
                    ],
                    char_to_map_name=DEFAULT_CHAR_TO_NAME,
                ),
            )
        )
        sim = Simulation(cfg)

        # Get tag ID mapping from the config
        id_map = cfg.game.id_map()
        tag_names = id_map.tag_names()
        tag_name_to_id = {name: idx for idx, name in enumerate(tag_names)}
        mobile_id = tag_name_to_id["mobile"]

        objects = sim._c_sim.grid_objects()

        # Find the agent
        agent_obj = None
        for _obj_id, obj_data in objects.items():
            if obj_data["type_name"] == "agent":
                agent_obj = obj_data
                break

        assert agent_obj is not None

        assert agent_obj["has_tag"](mobile_id) is True

        # Add 'mobile' again - should not cause errors or duplicate
        agent_obj["add_tag"](mobile_id)
        assert agent_obj["has_tag"](mobile_id) is True

    def test_remove_nonexistent_tag(self):
        """Removing a tag that doesn't exist should be a no-op."""
        cfg = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=3, height=3, num_tokens=100),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                agents=[AgentConfig(tags=["mobile"])],
                resource_names=[],
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        [".", ".", "."],
                        [".", "@", "."],
                        [".", ".", "."],
                    ],
                    char_to_map_name=DEFAULT_CHAR_TO_NAME,
                ),
            )
        )
        sim = Simulation(cfg)

        # Get tag ID mapping from the config
        id_map = cfg.game.id_map()
        tag_names = id_map.tag_names()
        tag_name_to_id = {name: idx for idx, name in enumerate(tag_names)}
        mobile_id = tag_name_to_id["mobile"]

        objects = sim._c_sim.grid_objects()

        # Find the agent
        agent_obj = None
        for _obj_id, obj_data in objects.items():
            if obj_data["type_name"] == "agent":
                agent_obj = obj_data
                break

        assert agent_obj is not None

        # Try to remove a tag that doesn't exist (tag ID 999)
        agent_obj["remove_tag"](999)

        # Should not cause errors, original tag still there
        assert agent_obj["has_tag"](mobile_id) is True


class TestTagIndexIntegration:
    """Tests for TagIndex integration with MettaGrid."""

    def test_tag_index_integration(self):
        """MettaGrid should populate TagIndex on object creation."""
        cfg = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=5, height=5, num_tokens=100),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                objects={
                    "wall_a": WallConfig(name="wall_a", map_name="wall_a", tags=["foo"]),
                    "wall_b": WallConfig(name="wall_b", map_name="wall_b", tags=["foo", "bar"]),
                },
                agents=[AgentConfig(tags=["mobile"])],
                resource_names=[],
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        [".", ".", ".", ".", "."],
                        [".", "A", ".", "A", "."],
                        [".", ".", "@", ".", "."],
                        [".", "B", ".", ".", "."],
                        [".", ".", ".", ".", "."],
                    ],
                    char_to_map_name={
                        ".": "empty",
                        "A": "wall_a",
                        "B": "wall_b",
                    },
                ),
            )
        )
        sim = Simulation(cfg)

        # Get the tag index from the MettaGrid
        tag_index = sim._c_sim.tag_index()

        # Get the ID map from the config to find tag IDs
        id_map = cfg.game.id_map()
        tag_names = id_map.tag_names()
        tag_name_to_id = {name: idx for idx, name in enumerate(tag_names)}

        # Get tag IDs (sorted alphabetically: bar=0, foo=1, mobile=2)
        foo_id = tag_name_to_id["foo"]
        bar_id = tag_name_to_id["bar"]

        # We have 2 wall_a objects (with tag "foo") and 1 wall_b object (with tags "foo" and "bar")
        # Total objects with tag "foo" should be 3
        # Total objects with tag "bar" should be 1
        assert tag_index.count_objects_with_tag(foo_id) == 3
        assert tag_index.count_objects_with_tag(bar_id) == 1

    def test_tag_index_syncs_with_add_remove(self):
        """TagIndex should update when tags are added/removed from objects."""
        cfg = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=3, height=3, num_tokens=100),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                objects={"wall": WallConfig(tags=["solid"])},
                agents=[AgentConfig(tags=["mobile"])],
                resource_names=[],
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        ["#", "#", "#"],
                        ["#", "@", "#"],
                        ["#", "#", "#"],
                    ],
                    char_to_map_name=DEFAULT_CHAR_TO_NAME,
                ),
            )
        )
        sim = Simulation(cfg)

        # Get the tag index and ID map
        tag_index = sim._c_sim.tag_index()
        id_map = cfg.game.id_map()
        tag_names = id_map.tag_names()
        tag_name_to_id = {name: idx for idx, name in enumerate(tag_names)}

        mobile_id = tag_name_to_id["mobile"]
        solid_id = tag_name_to_id["solid"]

        # Initially: 1 agent with "mobile", 8 walls with "solid"
        assert tag_index.count_objects_with_tag(mobile_id) == 1
        assert tag_index.count_objects_with_tag(solid_id) == 8

        # Find an agent and add "solid" tag
        objects = sim._c_sim.grid_objects()
        agent_obj = None
        for _obj_id, obj_data in objects.items():
            if obj_data["type_name"] == "agent":
                agent_obj = obj_data
                break

        assert agent_obj is not None
        agent_obj["add_tag"](solid_id)

        # Now should be 9 objects with "solid"
        assert tag_index.count_objects_with_tag(solid_id) == 9

        # Remove "mobile" from agent
        agent_obj["remove_tag"](mobile_id)

        # Now should be 0 objects with "mobile"
        assert tag_index.count_objects_with_tag(mobile_id) == 0


class TestOnTagAddedIntegration:
    """Integration tests for on_tag_added via AOE tag mutations."""

    def test_aoe_add_tag_updates_tag_index_count(self):
        """When AOE adds a tag, TagIndex count should reflect the change."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],
                ["#", ".", "S", ".", "#"],
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "tagger"},
        )
        cfg.game.actions.noop.enabled = True
        cfg.game.objects["tagger"] = GridObjectConfig(
            name="tagger",
            map_name="tagger",
            tags=["marked"],
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[],
                    mutations=[addTag("marked")],
                )
            },
        )

        sim = Simulation(cfg)
        tag_index = sim._c_sim.tag_index()
        id_map = cfg.game.id_map()
        tag_names = id_map.tag_names()
        tag_name_to_id = {name: idx for idx, name in enumerate(tag_names)}
        marked_id = tag_name_to_id["marked"]

        # tagger itself has "marked", agent does not yet
        initial_count = tag_index.count_objects_with_tag(marked_id)
        assert initial_count >= 1

        sim.agent(0).set_action("noop")
        sim.step()

        # After AOE fires, agent also has "marked"
        assert tag_index.count_objects_with_tag(marked_id) == initial_count + 1

    def test_add_tag_then_remove_tag_round_trip(self):
        """AOE add then manual remove should bring count back to original."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],
                ["#", ".", "S", ".", "#"],
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "tagger"},
        )
        cfg.game.actions.noop.enabled = True
        cfg.game.objects["tagger"] = GridObjectConfig(
            name="tagger",
            map_name="tagger",
            tags=["buff"],
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[],
                    mutations=[addTag("buff")],
                )
            },
        )

        sim = Simulation(cfg)
        tag_index = sim._c_sim.tag_index()
        id_map = cfg.game.id_map()
        tag_names = id_map.tag_names()
        tag_name_to_id = {name: idx for idx, name in enumerate(tag_names)}
        buff_id = tag_name_to_id["buff"]

        initial_count = tag_index.count_objects_with_tag(buff_id)

        # Step to apply the tag
        sim.agent(0).set_action("noop")
        sim.step()
        assert tag_index.count_objects_with_tag(buff_id) == initial_count + 1

        # Manually remove the tag from the agent
        objects = sim._c_sim.grid_objects()
        for _obj_id, obj_data in objects.items():
            if obj_data["type_name"] == "agent":
                obj_data["remove_tag"](buff_id)
                break

        assert tag_index.count_objects_with_tag(buff_id) == initial_count


class TestOnTagRemovedIntegration:
    """Integration tests for on_tag_removed via AOE tag mutations and on_tag_remove handlers."""

    def test_aoe_remove_tag_updates_tag_index_count(self):
        """When AOE removes a tag, TagIndex count should reflect the change."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],
                ["#", ".", "S", ".", "#"],
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "cleanser"},
        )
        cfg.game.agent.tags = ["cursed"]
        cfg.game.actions.noop.enabled = True
        cfg.game.objects["cleanser"] = GridObjectConfig(
            name="cleanser",
            map_name="cleanser",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[],
                    mutations=[removeTag("cursed")],
                )
            },
        )

        sim = Simulation(cfg)
        tag_index = sim._c_sim.tag_index()
        id_map = cfg.game.id_map()
        tag_names = id_map.tag_names()
        tag_name_to_id = {name: idx for idx, name in enumerate(tag_names)}
        cursed_id = tag_name_to_id["cursed"]

        # Agent starts with "cursed"
        assert tag_index.count_objects_with_tag(cursed_id) == 1

        sim.agent(0).set_action("noop")
        sim.step()

        # After AOE fires, agent no longer has "cursed"
        assert tag_index.count_objects_with_tag(cursed_id) == 0

    def test_on_tag_remove_handler_fires_on_removal(self):
        """on_tag_remove handler should fire and apply mutations when tag is removed."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],
                ["#", ".", "S", ".", "#"],
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "cleanser"},
        )
        cfg.game.resource_names = ["gold"]
        cfg.game.agent.tags = ["enchanted"]
        cfg.game.agent.inventory.initial = {"gold": 0}
        cfg.game.agent.inventory.limits = {
            "gold": ResourceLimitsConfig(min=1000, resources=["gold"]),
        }
        # When "enchanted" is removed, agent gains 50 gold
        cfg.game.agent.on_tag_remove = {
            "enchanted": Handler(
                mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"gold": 50})],
            ),
        }
        cfg.game.actions.noop.enabled = True
        cfg.game.objects["cleanser"] = GridObjectConfig(
            name="cleanser",
            map_name="cleanser",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[],
                    mutations=[removeTag("enchanted")],
                )
            },
        )

        sim = Simulation(cfg)

        # Agent starts with 0 gold and "enchanted" tag
        assert sim.agent(0).inventory.get("gold", 0) == 0

        sim.agent(0).set_action("noop")
        sim.step()

        # on_tag_remove handler should have given 50 gold
        assert sim.agent(0).inventory.get("gold", 0) == 50

    def test_on_tag_remove_handler_does_not_fire_without_removal(self):
        """on_tag_remove handler should NOT fire if the tag is not removed."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#"],
                ["#", "@", "#"],
                ["#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty"},
        )
        cfg.game.resource_names = ["gold"]
        cfg.game.agent.tags = ["enchanted"]
        cfg.game.agent.inventory.initial = {"gold": 0}
        cfg.game.agent.inventory.limits = {
            "gold": ResourceLimitsConfig(min=1000, resources=["gold"]),
        }
        cfg.game.agent.on_tag_remove = {
            "enchanted": Handler(
                mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"gold": 50})],
            ),
        }
        cfg.game.actions.noop.enabled = True

        sim = Simulation(cfg)

        # No cleanser object — tag is never removed
        sim.agent(0).set_action("noop")
        sim.step()

        # Handler should not have fired
        assert sim.agent(0).inventory.get("gold", 0) == 0

    def test_tag_index_consistent_through_add_remove_cycle(self):
        """TagIndex counts should remain consistent through repeated add/remove cycles."""
        cfg = MettaGridConfig(
            game=GameConfig(
                num_agents=2,
                obs=ObsConfig(width=5, height=5, num_tokens=100),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                agents=[AgentConfig(tags=["mobile", "trackable"])],
                resource_names=[],
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        [".", ".", "."],
                        [".", "@", "."],
                        [".", "@", "."],
                    ],
                    char_to_map_name=DEFAULT_CHAR_TO_NAME,
                ),
            )
        )
        sim = Simulation(cfg)
        tag_index = sim._c_sim.tag_index()
        id_map = cfg.game.id_map()
        tag_names = id_map.tag_names()
        tag_name_to_id = {name: idx for idx, name in enumerate(tag_names)}
        trackable_id = tag_name_to_id["trackable"]

        # 2 agents both have "trackable"
        assert tag_index.count_objects_with_tag(trackable_id) == 2

        # Remove from first agent
        objects = sim._c_sim.grid_objects()
        agents = [obj_data for _oid, obj_data in objects.items() if obj_data["type_name"] == "agent"]
        assert len(agents) == 2

        agents[0]["remove_tag"](trackable_id)
        assert tag_index.count_objects_with_tag(trackable_id) == 1

        # Re-add to first agent
        agents[0]["add_tag"](trackable_id)
        assert tag_index.count_objects_with_tag(trackable_id) == 2

        # Remove from both
        agents[0]["remove_tag"](trackable_id)
        agents[1]["remove_tag"](trackable_id)
        assert tag_index.count_objects_with_tag(trackable_id) == 0

        # Add back to both
        agents[0]["add_tag"](trackable_id)
        agents[1]["add_tag"](trackable_id)
        assert tag_index.count_objects_with_tag(trackable_id) == 2
