"""Tests for TagIndex class."""

from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    AgentConfig,
    GameConfig,
    MettaGridConfig,
    NoopActionConfig,
    ObsConfig,
    WallConfig,
)
from mettagrid.config.tag import Tag
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
                objects={"wall": WallConfig(tags=[Tag("solid"), Tag("blocking")])},
                agents=[AgentConfig(tags=[Tag("mobile"), Tag("player")])],
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
                objects={"wall": WallConfig(tags=[Tag("solid")])},
                agents=[AgentConfig(tags=[Tag("mobile")])],
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
                objects={"wall": WallConfig(tags=[Tag("solid")])},
                agents=[AgentConfig(tags=[Tag("mobile"), Tag("player")])],
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
                agents=[AgentConfig(tags=[Tag("mobile")])],
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
                agents=[AgentConfig(tags=[Tag("mobile")])],
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
                    "wall_a": WallConfig(name="wall_a", map_name="wall_a", tags=[Tag("foo")]),
                    "wall_b": WallConfig(name="wall_b", map_name="wall_b", tags=[Tag("foo"), Tag("bar")]),
                },
                agents=[AgentConfig(tags=[Tag("mobile")])],
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
                objects={"wall": WallConfig(tags=[Tag("solid")])},
                agents=[AgentConfig(tags=[Tag("mobile")])],
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
