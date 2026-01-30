"""Tests for grid_objects() method properties and ignore_types parameter."""

import numpy as np
import pytest

from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    ChestConfig,
    GameConfig,
    MettaGridConfig,
    MoveActionConfig,
    NoopActionConfig,
    ObsConfig,
    WallConfig,
)
from mettagrid.map_builder.random_map import RandomMapBuilder
from mettagrid.simulator import BoundingBox, Simulation


@pytest.fixture
def sim_with_chest():
    """Create simulation with a chest to test chest properties."""
    config = MettaGridConfig(
        game=GameConfig(
            num_agents=1,
            obs=ObsConfig(width=5, height=5, num_tokens=100),
            max_steps=100,
            resource_names=["gold", "silver"],
            actions=ActionsConfig(noop=NoopActionConfig(), move=MoveActionConfig()),
            objects={
                "wall": WallConfig(),
                "chest": ChestConfig(vibe_transfers={}),
            },
            map_builder=RandomMapBuilder.Config(
                width=10,
                height=10,
                agents=1,
                objects={"chest": 1},  # Add one chest
                seed=42,
            ),
        )
    )
    return Simulation(config)


@pytest.fixture
def sim_with_walls():
    """Create simulation with walls to test ignore_types."""
    config = MettaGridConfig(
        game=GameConfig(
            num_agents=2,
            obs=ObsConfig(width=5, height=5, num_tokens=50),
            max_steps=10,
            actions=ActionsConfig(noop=NoopActionConfig(), move=MoveActionConfig()),
            objects={
                "wall": WallConfig(),
            },
            map_builder=RandomMapBuilder.Config(
                width=15,
                height=15,
                agents=2,
                objects={"wall": 20},  # Add 20 random walls
                border_width=1,  # Add border walls
                seed=123,
            ),
        )
    )
    return Simulation(config)


class TestIgnoreTypes:
    """Test ignore_types parameter for filtering objects."""

    def test_ignore_types_walls(self, sim_with_walls):
        """Test that ignore_types=['wall'] correctly filters out walls."""

        # Get all objects
        all_objects = sim_with_walls.grid_objects()
        print(f"All objects count: {len(all_objects)}")

        # Get objects without walls
        no_walls = sim_with_walls.grid_objects(ignore_types=["wall"])
        print(f"Objects without walls: {len(no_walls)}")

        # Count walls manually
        wall_count = sum(1 for obj in all_objects.values() if obj.get("type_name") == "wall")
        agent_count = sum(1 for obj in all_objects.values() if obj.get("type_name") == "agent")

        print(f"Wall count: {wall_count}")
        print(f"Agent count: {agent_count}")

        # Verify filtering worked
        assert len(all_objects) - len(no_walls) == wall_count, "Filtered count should match wall count"

        # Verify no walls remain in filtered result
        remaining_types = set(obj.get("type_name") for obj in no_walls.values())
        assert "wall" not in remaining_types, "No walls should remain after filtering"

        # Verify agents are still there
        agent_count_filtered = sum(1 for obj in no_walls.values() if obj.get("type_name") == "agent")
        assert agent_count_filtered == agent_count, "All agents should still be present"

    def test_ignore_multiple_types(self, sim_with_walls):
        """Test ignoring multiple object types."""

        all_objects = sim_with_walls.grid_objects()

        # Filter out both walls and agents
        no_walls_or_agents = sim_with_walls.grid_objects(ignore_types=["wall", "agent"])

        # Count types
        wall_count = sum(1 for obj in all_objects.values() if obj.get("type_name") == "wall")
        agent_count = sum(1 for obj in all_objects.values() if obj.get("type_name") == "agent")

        # Should have filtered out all objects in this simple environment
        expected_remaining = len(all_objects) - wall_count - agent_count
        assert len(no_walls_or_agents) == expected_remaining

    def test_ignore_with_bounding_box(self, sim_with_walls):
        """Test that ignore_types works with bounding box filtering."""

        bbox = BoundingBox(min_row=0, max_row=5, min_col=0, max_col=5)

        # Get objects in bbox
        bbox_objects = sim_with_walls.grid_objects(bbox=bbox)

        # Get objects in bbox without walls
        bbox_no_walls = sim_with_walls.grid_objects(bbox=bbox, ignore_types=["wall"])

        # Count walls in bbox
        wall_count = sum(1 for obj in bbox_objects.values() if obj.get("type_name") == "wall")

        assert len(bbox_objects) - len(bbox_no_walls) == wall_count


class TestChestProperties:
    """Test chest-specific properties in grid_objects."""

    def test_chest_basic_properties(self, sim_with_chest):
        """Test that chest properties are exposed."""

        objects = sim_with_chest.grid_objects()

        # Find a chest
        chest = next((obj for obj in objects.values() if obj.get("type_name") == "chest"), None)

        if chest:
            # Check chest-specific properties
            assert "vibe_transfers" in chest

            # Check values match config
            vibe_transfers = chest["vibe_transfers"]
            assert isinstance(vibe_transfers, dict)

            # Check that chest has inventory dict
            assert "inventory" in chest
            assert isinstance(chest["inventory"], dict)


class TestAgentProperties:
    """Test that all agent properties are properly exposed."""

    def test_agent_properties(self, sim_with_walls):
        """Test that all agent properties are exposed."""

        objects = sim_with_walls.grid_objects()

        # Find an agent
        agent = next((obj for obj in objects.values() if obj.get("type_name") == "agent"), None)

        assert agent is not None, "Should have at least one agent"

        # Check all agent properties that are exposed
        required_properties = [
            "agent_id",
            "agent:group",  # Group ID (prefixed)
            "agent:frozen",  # Frozen ticks remaining (prefixed)
            "group_id",  # Also available without prefix
            "group_name",
            "freeze_duration",
            "freeze_remaining",
            "is_frozen",  # Boolean version
            "inventory",
            "vibe",
        ]

        for prop in required_properties:
            assert prop in agent, f"Agent should have {prop} property"

        # Check types
        assert isinstance(agent["agent_id"], (int, np.integer))
        assert isinstance(agent["agent:group"], (int, np.integer))
        assert isinstance(agent["agent:frozen"], (int, np.integer))  # frozen is an integer (ticks remaining)
        assert isinstance(agent["group_id"], (int, np.integer))
        assert isinstance(agent["is_frozen"], bool)
        assert isinstance(agent["freeze_remaining"], (int, np.integer))
        assert isinstance(agent["freeze_duration"], (int, np.integer))
        assert isinstance(agent["inventory"], dict)
