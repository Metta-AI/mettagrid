#!/usr/bin/env python3
"""End-to-end tests for event behavior in simulation.

These tests verify that events actually behave correctly at runtime,
not just that the config is converted properly.
"""

import pytest

from mettagrid.config.event_config import EventConfig
from mettagrid.config.filter import (
    isA,
    isAlignedTo,
    isNotAlignedTo,
)
from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    CollectiveConfig,
    GameConfig,
    MettaGridConfig,
    NoopActionConfig,
    ObsConfig,
    WallConfig,
)
from mettagrid.config.mutation import alignTo, removeAlignment
from mettagrid.config.query import query
from mettagrid.map_builder.ascii import AsciiMapBuilder
from mettagrid.mapgen.utils.ascii_grid import DEFAULT_CHAR_TO_NAME
from mettagrid.simulator import Simulation


class TestEventMaxTargetsSimulation:
    """Test that max_targets actually limits affected objects in simulation."""

    def _count_objects_by_collective(self, sim: Simulation, object_type: str) -> dict[int, int]:
        """Count objects of given type by their collective_id."""
        objects = sim.grid_objects()
        matching = [obj for obj in objects.values() if obj.get("type_name") == object_type]
        collectives: dict[int, int] = {}
        for obj in matching:
            cid = obj.get("collective_id", -1)
            collectives[cid] = collectives.get(cid, 0) + 1
        return collectives

    def test_max_targets_1_limits_to_one_object(self):
        """Test that max_targets=1 only affects one object.

        This was the main symptom - events were affecting ALL matching objects
        instead of just 1 when max_targets=1.
        """
        # Create config with multiple walls and an event that should only affect 1
        config = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=7, height=7, num_tokens=100),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                resource_names=[],
                objects={
                    "wall": WallConfig(tags=["type:wall"]),
                },
                collectives={
                    "clips": CollectiveConfig(),
                },
                events={
                    "align_one_wall": EventConfig(
                        name="align_one_wall",
                        target_query=query("type:wall"),
                        timesteps=[5],  # Fire at timestep 5
                        filters=[isA("wall")],
                        mutations=[alignTo("clips")],
                        max_targets=1,  # Should only affect 1 wall
                    ),
                },
                map_builder=AsciiMapBuilder.Config(
                    # Place multiple walls in a grid
                    map_data=[
                        ["#", "#", "#", "#", "#", "#", "#"],
                        ["#", ".", ".", ".", ".", ".", "#"],
                        ["#", ".", "#", ".", "#", ".", "#"],
                        ["#", ".", ".", "@", ".", ".", "#"],
                        ["#", ".", "#", ".", "#", ".", "#"],
                        ["#", ".", ".", ".", ".", ".", "#"],
                        ["#", "#", "#", "#", "#", "#", "#"],
                    ],
                    char_to_map_name=DEFAULT_CHAR_TO_NAME,
                ),
            ),
        )

        sim = Simulation(config)

        # Count walls before event fires
        before = self._count_objects_by_collective(sim, "wall")
        clips_id = None
        for cid in before:
            if cid != -1:
                clips_id = cid

        initial_clips_walls = before.get(clips_id, 0) if clips_id else 0

        # Step past the event timestep
        for _ in range(6):
            sim.step()

        # Count walls after event fires
        after = self._count_objects_by_collective(sim, "wall")

        # Find how many walls are now aligned to clips
        clips_walls_after = sum(count for cid, count in after.items() if cid != -1)

        # With max_targets=1, only 1 additional wall should be aligned
        assert clips_walls_after == initial_clips_walls + 1, (
            f"Expected exactly 1 wall to be aligned (was {initial_clips_walls}, now {clips_walls_after}), "
            f"but got {clips_walls_after - initial_clips_walls} walls affected"
        )

    def test_max_targets_0_affects_all_objects(self):
        """Test that max_targets=0 (unlimited) affects all matching objects."""
        # Create config with multiple walls and an event that should affect all
        config = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=5, height=5, num_tokens=100),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                resource_names=[],
                objects={
                    "wall": WallConfig(tags=["type:wall"]),
                },
                collectives={
                    "clips": CollectiveConfig(),
                },
                events={
                    "align_all_walls": EventConfig(
                        name="align_all_walls",
                        target_query=query("type:wall"),
                        timesteps=[5],
                        filters=[isA("wall"), isAlignedTo(None)],  # Only unaligned walls
                        mutations=[alignTo("clips")],
                        max_targets=None,  # Unlimited
                    ),
                },
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        ["#", "#", "#", "#", "#"],
                        ["#", ".", ".", ".", "#"],
                        ["#", ".", "@", ".", "#"],
                        ["#", ".", ".", ".", "#"],
                        ["#", "#", "#", "#", "#"],
                    ],
                    char_to_map_name=DEFAULT_CHAR_TO_NAME,
                ),
            ),
        )

        sim = Simulation(config)

        # Step past the event timestep
        for _ in range(6):
            sim.step()

        # Count walls after
        after = self._count_objects_by_collective(sim, "wall")
        unaligned_after = after.get(-1, 0)

        # All previously unaligned walls should now be aligned
        assert unaligned_after == 0, f"Expected all walls to be aligned, but {unaligned_after} still unaligned"

    def test_max_targets_5_limits_to_five_objects(self):
        """Test that max_targets=5 only affects up to 5 objects."""
        # Create config with many walls
        config = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=11, height=11, num_tokens=100),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                resource_names=[],
                objects={
                    "wall": WallConfig(tags=["type:wall"]),
                },
                collectives={
                    "clips": CollectiveConfig(),
                },
                events={
                    "align_five_walls": EventConfig(
                        name="align_five_walls",
                        target_query=query("type:wall"),
                        timesteps=[5],
                        filters=[isA("wall")],
                        mutations=[alignTo("clips")],
                        max_targets=5,  # Should only affect up to 5 walls
                    ),
                },
                map_builder=AsciiMapBuilder.Config(
                    # Create a grid with many walls (outer ring = lots of walls)
                    map_data=[
                        ["#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#"],
                        ["#", ".", ".", ".", ".", ".", ".", ".", ".", ".", "#"],
                        ["#", ".", ".", ".", ".", ".", ".", ".", ".", ".", "#"],
                        ["#", ".", ".", ".", ".", ".", ".", ".", ".", ".", "#"],
                        ["#", ".", ".", ".", ".", ".", ".", ".", ".", ".", "#"],
                        ["#", ".", ".", ".", ".", "@", ".", ".", ".", ".", "#"],
                        ["#", ".", ".", ".", ".", ".", ".", ".", ".", ".", "#"],
                        ["#", ".", ".", ".", ".", ".", ".", ".", ".", ".", "#"],
                        ["#", ".", ".", ".", ".", ".", ".", ".", ".", ".", "#"],
                        ["#", ".", ".", ".", ".", ".", ".", ".", ".", ".", "#"],
                        ["#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#"],
                    ],
                    char_to_map_name=DEFAULT_CHAR_TO_NAME,
                ),
            ),
        )

        sim = Simulation(config)

        # Count walls before
        before = self._count_objects_by_collective(sim, "wall")
        total_walls = sum(before.values())
        assert total_walls > 5, f"Need more than 5 walls to test, got {total_walls}"

        # Step past the event timestep
        for _ in range(6):
            sim.step()

        # Count walls aligned after
        after = self._count_objects_by_collective(sim, "wall")
        aligned_after = sum(count for cid, count in after.items() if cid != -1)

        # Should have exactly 5 walls aligned
        assert aligned_after == 5, f"Expected exactly 5 walls to be aligned, but got {aligned_after}"


class TestEventFilterSimulation:
    """Test that filters actually work in simulation."""

    def _count_objects_by_collective(self, sim: Simulation, object_type: str) -> dict[int, int]:
        """Count objects of given type by their collective_id."""
        objects = sim.grid_objects()
        matching = [obj for obj in objects.values() if obj.get("type_name") == object_type]
        collectives: dict[int, int] = {}
        for obj in matching:
            cid = obj.get("collective_id", -1)
            collectives[cid] = collectives.get(cid, 0) + 1
        return collectives

    def test_alignment_filter_only_affects_unaligned(self):
        """Test that isAlignedTo(None) filter only matches unaligned objects."""
        # Create config where some walls start aligned and some don't
        config = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=5, height=5, num_tokens=100),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                resource_names=[],
                objects={
                    # wall type that starts unaligned
                    "wall": WallConfig(tags=["type:wall"]),
                    # aligned_wall type that starts aligned
                    "aligned_wall": WallConfig(tags=["type:wall"], collective="cogs"),
                },
                collectives={
                    "cogs": CollectiveConfig(),
                    "clips": CollectiveConfig(),
                },
                events={
                    "align_unaligned_only": EventConfig(
                        name="align_unaligned_only",
                        target_query=query("type:wall"),
                        timesteps=[5],
                        filters=[isA("wall"), isAlignedTo(None)],  # Only unaligned
                        mutations=[alignTo("clips")],
                        max_targets=None,  # Affect all matching
                    ),
                },
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        ["#", "#", "#", "#", "#"],  # These are unaligned walls
                        ["#", ".", ".", ".", "#"],
                        ["#", ".", "@", ".", "#"],
                        ["#", ".", ".", ".", "#"],
                        ["#", "#", "#", "#", "#"],
                    ],
                    char_to_map_name=DEFAULT_CHAR_TO_NAME,
                ),
            ),
        )

        sim = Simulation(config)

        # Step past event
        for _ in range(6):
            sim.step()

        # Get counts after
        after = self._count_objects_by_collective(sim, "wall")

        # All unaligned walls should now be aligned to clips
        # The originally aligned walls (to cogs) should still be aligned to cogs
        unaligned_after = after.get(-1, 0)
        assert unaligned_after == 0, f"All unaligned walls should be aligned now, but {unaligned_after} remain"

    def test_is_not_aligned_to_filter_excludes_collective(self):
        """Test that isNotAlignedTo filter excludes objects aligned to the specified collective.

        This verifies the fix for the C++ NegFilter collective_id conversion bug.

        Setup:
        - 4 walls aligned to "clips"
        - 4 walls aligned to "cogs"
        - Event with isNotAlignedTo("clips") filter that removes alignment

        Expected:
        - Only cogs-aligned walls should have alignment removed (not clips)
        - Clips-aligned walls should remain unchanged
        """
        config = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=5, height=5, num_tokens=100),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                resource_names=[],
                objects={
                    "clips_wall": WallConfig(name="clips_wall", map_name="C", tags=["type:wall"], collective="clips"),
                    "cogs_wall": WallConfig(name="cogs_wall", map_name="G", tags=["type:wall"], collective="cogs"),
                },
                collectives={
                    "cogs": CollectiveConfig(),
                    "clips": CollectiveConfig(),
                },
                events={
                    "scramble_non_clips": EventConfig(
                        name="scramble_non_clips",
                        target_query=query("type:wall"),
                        timesteps=[5],
                        filters=[isNotAlignedTo("clips")],  # Should exclude clips-aligned
                        mutations=[removeAlignment()],  # Remove alignment
                        max_targets=None,  # Affect all matching
                    ),
                },
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        ["C", "C", ".", "G", "G"],  # C = clips_wall, G = cogs_wall
                        [".", ".", ".", ".", "."],
                        [".", ".", "@", ".", "."],
                        [".", ".", ".", ".", "."],
                        ["C", "C", ".", "G", "G"],
                    ],
                    char_to_map_name={
                        "#": "wall",
                        ".": "empty",
                        "@": "agent.agent",
                        "C": "C",
                        "G": "G",
                    },
                ),
            ),
        )

        sim = Simulation(config)

        # Get collective IDs from objects
        def get_collective_id(name: str) -> int:
            for obj in sim.grid_objects().values():
                if obj.get("collective_name") == name:
                    return obj.get("collective_id", -1)
            return -1

        clips_id = get_collective_id("clips")
        cogs_id = get_collective_id("cogs")
        assert clips_id != -1, "Clips collective should exist"
        assert cogs_id != -1, "Cogs collective should exist"

        # Count walls by collective - use type_name from the objects
        def count_walls_by_collective() -> dict[int, int]:
            objects = sim.grid_objects()
            collectives: dict[int, int] = {}
            for obj in objects.values():
                # Match both wall types by checking if name contains "wall"
                if "wall" in obj.get("type_name", ""):
                    cid = obj.get("collective_id", -1)
                    collectives[cid] = collectives.get(cid, 0) + 1
            return collectives

        # Count before event
        before = count_walls_by_collective()
        assert before.get(clips_id, 0) == 4, f"Expected 4 clips walls, got {before.get(clips_id, 0)}"
        assert before.get(cogs_id, 0) == 4, f"Expected 4 cogs walls, got {before.get(cogs_id, 0)}"

        # Step past event
        for _ in range(6):
            sim.step()

        # Count after event
        after = count_walls_by_collective()

        # Clips walls should still be aligned to clips (NOT affected by isNotAlignedTo("clips"))
        assert after.get(clips_id, 0) == 4, (
            f"Clips walls should remain aligned to clips, but only {after.get(clips_id, 0)} remain"
        )

        # Cogs walls should now be unaligned (affected by the event)
        assert after.get(cogs_id, 0) == 0, f"Cogs walls should be unaligned, but {after.get(cogs_id, 0)} remain aligned"

        # Should have 4 unaligned walls now (the former cogs walls)
        unaligned_after = after.get(-1, 0)
        assert unaligned_after == 4, f"Expected 4 unaligned walls, got {unaligned_after}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
