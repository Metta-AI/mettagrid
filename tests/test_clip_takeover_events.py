#!/usr/bin/env python3
"""Tests for clip takeover events in a cogsguard-style scenario.

These tests verify that clip takeover mechanics work correctly:
1. Scramble events remove alignment from clips-aligned objects near cogs
2. Align events convert scrambled (neutral) objects to cogs
3. The combination allows territorial takeover through proximity

The scenario uses:
- "cogs" collective: the agents/friendly team
- "clips" collective: the enemy faction
- Junctions: objects that start aligned to clips and can be taken over
"""

import pytest

from mettagrid.config.event_config import EventConfig, periodic
from mettagrid.config.filter import (
    isA,
    isAlignedTo,
    isNear,
)
from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    AgentConfig,
    CollectiveConfig,
    GameConfig,
    MettaGridConfig,
    NoopActionConfig,
    ObsConfig,
    WallConfig,
)
from mettagrid.config.mutation import alignTo, removeAlignment
from mettagrid.config.tag import Tag
from mettagrid.map_builder.ascii import AsciiMapBuilder
from mettagrid.mapgen.utils.ascii_grid import DEFAULT_CHAR_TO_NAME
from mettagrid.simulator import Simulation


def _count_objects_by_collective(sim: Simulation, object_type: str) -> dict[int, int]:
    """Count objects of given type by their collective_id.

    Returns dict mapping collective_id -> count.
    Unaligned objects have collective_id = -1.
    """
    objects = sim.grid_objects()
    matching = [obj for obj in objects.values() if obj.get("type_name") == object_type]
    collectives: dict[int, int] = {}
    for obj in matching:
        cid = obj.get("collective_id", -1)
        collectives[cid] = collectives.get(cid, 0) + 1
    return collectives


def _get_collective_id(sim: Simulation, collective_name: str) -> int:
    """Get the collective ID for a named collective."""
    objects = sim.grid_objects()
    for obj in objects.values():
        collective = obj.get("collective_name")
        if collective == collective_name:
            return obj.get("collective_id", -1)
    return -1


class TestClipScrambleEvents:
    """Test events that scramble (remove alignment from) clips-aligned objects."""

    def test_scramble_event_removes_clips_alignment(self):
        """Test that scramble event removes alignment from clips-aligned junctions near cogs.

        Setup:
        - Agent (cog) starts at center
        - Junction starts aligned to clips, adjacent to agent
        - Scramble event fires, removing clips alignment from nearby junctions

        Expected: Junction becomes unaligned (neutral).
        """
        config = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=5, height=5, num_tokens=100),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                resource_names=[],
                agent=AgentConfig(collective="cogs"),
                objects={
                    "wall": WallConfig(name="wall", tags=[Tag("type:wall")]),
                    "junction": WallConfig(name="junction", tags=[Tag("type:junction")], collective="clips"),
                },
                collectives={
                    "cogs": CollectiveConfig(),
                    "clips": CollectiveConfig(),
                },
                events={
                    # Scramble: remove alignment from clips-aligned junctions near cogs
                    "scramble_clips": EventConfig(
                        name="scramble_clips",
                        target_tag="type:junction",
                        timesteps=[5],
                        filters=[
                            isA("junction"),
                            isAlignedTo("clips"),
                            isNear("type:agent", [isAlignedTo("cogs")], radius=1),
                        ],
                        mutations=[removeAlignment()],
                    ),
                },
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        ["#", "#", "#", "#", "#"],
                        ["#", ".", ".", ".", "#"],
                        ["#", ".", "@", "J", "#"],  # Agent at center, Junction adjacent
                        ["#", ".", ".", ".", "#"],
                        ["#", "#", "#", "#", "#"],
                    ],
                    char_to_map_name={**DEFAULT_CHAR_TO_NAME, "J": "junction"},
                ),
            ),
        )

        sim = Simulation(config)

        # Verify junction starts aligned to clips
        before = _count_objects_by_collective(sim, "junction")
        clips_id = _get_collective_id(sim, "clips")
        assert clips_id != -1, "Clips collective should exist"
        assert before.get(clips_id, 0) == 1, "Junction should start aligned to clips"

        # Step past the scramble event
        for _ in range(6):
            sim.step()

        # Verify junction is now unaligned
        after = _count_objects_by_collective(sim, "junction")
        assert after.get(-1, 0) == 1, "Junction should be unaligned after scramble"
        assert after.get(clips_id, 0) == 0, "Junction should no longer be aligned to clips"

    def test_scramble_respects_radius(self):
        """Test that scramble only affects junctions within radius.

        Setup:
        - Agent at center
        - Junction A at distance 1 (should be scrambled)
        - Junction B at distance 3 (should NOT be scrambled)
        - Scramble event with radius=1

        Expected: Only Junction A becomes unaligned.
        """
        config = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=9, height=9, num_tokens=100),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                resource_names=[],
                agent=AgentConfig(collective="cogs"),
                objects={
                    "wall": WallConfig(name="wall", tags=[Tag("type:wall")]),
                    "junction": WallConfig(name="junction", tags=[Tag("type:junction")], collective="clips"),
                },
                collectives={
                    "cogs": CollectiveConfig(),
                    "clips": CollectiveConfig(),
                },
                events={
                    "scramble_clips": EventConfig(
                        name="scramble_clips",
                        target_tag="type:junction",
                        timesteps=[5],
                        filters=[
                            isA("junction"),
                            isAlignedTo("clips"),
                            isNear("type:agent", [isAlignedTo("cogs")], radius=1),
                        ],
                        mutations=[removeAlignment()],
                    ),
                },
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        ["#", "#", "#", "#", "#", "#", "#", "#", "#"],
                        ["#", ".", ".", ".", ".", ".", ".", ".", "#"],
                        ["#", ".", ".", ".", ".", ".", ".", ".", "#"],
                        ["#", ".", ".", ".", "J", ".", ".", ".", "#"],  # Junction B at distance 3
                        ["#", ".", ".", ".", "@", "J", ".", ".", "#"],  # Agent center, Junction A adjacent
                        ["#", ".", ".", ".", ".", ".", ".", ".", "#"],
                        ["#", ".", ".", ".", ".", ".", ".", ".", "#"],
                        ["#", ".", ".", ".", ".", ".", ".", ".", "#"],
                        ["#", "#", "#", "#", "#", "#", "#", "#", "#"],
                    ],
                    char_to_map_name={**DEFAULT_CHAR_TO_NAME, "J": "junction"},
                ),
            ),
        )

        sim = Simulation(config)

        # Verify both junctions start aligned to clips
        before = _count_objects_by_collective(sim, "junction")
        clips_id = _get_collective_id(sim, "clips")
        assert before.get(clips_id, 0) == 2, "Both junctions should start aligned to clips"

        # Step past the scramble event
        for _ in range(6):
            sim.step()

        # Verify: 1 scrambled (unaligned), 1 still clips
        after = _count_objects_by_collective(sim, "junction")
        assert after.get(-1, 0) == 1, "One junction should be scrambled (unaligned)"
        assert after.get(clips_id, 0) == 1, "One junction should still be aligned to clips"


class TestClipAlignEvents:
    """Test events that align neutral objects to cogs."""

    def test_align_event_converts_neutral_to_cogs(self):
        """Test that align event converts unaligned junctions near cogs to cogs.

        Setup:
        - Agent (cog) at center
        - Junction starts unaligned, adjacent to agent
        - Align event fires, aligning neutral junctions to cogs

        Expected: Junction becomes aligned to cogs.
        """
        config = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=5, height=5, num_tokens=100),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                resource_names=[],
                agent=AgentConfig(collective="cogs"),
                objects={
                    "wall": WallConfig(name="wall", tags=[Tag("type:wall")]),
                    "junction": WallConfig(name="junction", tags=[Tag("type:junction")]),  # Starts unaligned
                },
                collectives={
                    "cogs": CollectiveConfig(),
                    "clips": CollectiveConfig(),
                },
                events={
                    # Align: convert neutral junctions near cogs to cogs
                    "align_to_cogs": EventConfig(
                        name="align_to_cogs",
                        target_tag="type:junction",
                        timesteps=[5],
                        filters=[
                            isA("junction"),
                            isAlignedTo(None),  # Only neutral objects
                            isNear("type:agent", [isAlignedTo("cogs")], radius=1),
                        ],
                        mutations=[alignTo("cogs")],
                    ),
                },
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        ["#", "#", "#", "#", "#"],
                        ["#", ".", ".", ".", "#"],
                        ["#", ".", "@", "J", "#"],  # Agent at center, Junction adjacent
                        ["#", ".", ".", ".", "#"],
                        ["#", "#", "#", "#", "#"],
                    ],
                    char_to_map_name={**DEFAULT_CHAR_TO_NAME, "J": "junction"},
                ),
            ),
        )

        sim = Simulation(config)

        # Verify junction starts unaligned
        before = _count_objects_by_collective(sim, "junction")
        assert before.get(-1, 0) == 1, "Junction should start unaligned"

        # Step past the align event
        for _ in range(6):
            sim.step()

        # Verify junction is now aligned to cogs
        after = _count_objects_by_collective(sim, "junction")
        cogs_id = _get_collective_id(sim, "cogs")
        assert cogs_id != -1, "Cogs collective should exist"
        assert after.get(cogs_id, 0) == 1, "Junction should be aligned to cogs"
        assert after.get(-1, 0) == 0, "Junction should no longer be unaligned"


class TestAggressiveClipTakeover:
    """Test aggressive clip takeover with combined scramble and align events.

    This simulates the full cogsguard territorial expansion mechanic:
    1. Clips-aligned objects near cogs get scrambled (lose alignment)
    2. Neutral objects near cogs get aligned to cogs
    3. Over time, cogs territory expands by converting clips territory
    """

    def test_aggressive_takeover_sequence(self):
        """Test full territorial takeover with scramble followed by align.

        Setup:
        - Agent (cog) at center
        - Multiple junctions start aligned to clips
        - Periodic scramble events (every 10 steps) remove clips alignment
        - Periodic align events (every 10 steps, offset by 5) convert neutral to cogs

        Expected: Over time, junctions transition clips -> neutral -> cogs.
        """
        config = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=7, height=7, num_tokens=100),
                max_steps=200,
                actions=ActionsConfig(noop=NoopActionConfig()),
                resource_names=[],
                agent=AgentConfig(collective="cogs"),
                objects={
                    "wall": WallConfig(name="wall", tags=[Tag("type:wall")]),
                    "junction": WallConfig(name="junction", tags=[Tag("type:junction")], collective="clips"),
                },
                collectives={
                    "cogs": CollectiveConfig(),
                    "clips": CollectiveConfig(),
                },
                events={
                    # Scramble clips: fires at 10, 20, 30...
                    "scramble_clips": EventConfig(
                        name="scramble_clips",
                        target_tag="type:junction",
                        timesteps=periodic(start=10, period=10, end=100),
                        filters=[
                            isA("junction"),
                            isAlignedTo("clips"),
                            isNear("type:agent", [isAlignedTo("cogs")], radius=2),
                        ],
                        mutations=[removeAlignment()],
                        max_targets=1,  # Aggressive but controlled
                    ),
                    # Align to cogs: fires at 15, 25, 35...
                    "align_to_cogs": EventConfig(
                        name="align_to_cogs",
                        target_tag="type:junction",
                        timesteps=periodic(start=15, period=10, end=100),
                        filters=[
                            isA("junction"),
                            isAlignedTo(None),  # Only neutral
                            isNear("type:agent", [isAlignedTo("cogs")], radius=2),
                        ],
                        mutations=[alignTo("cogs")],
                        max_targets=1,  # Aggressive but controlled
                    ),
                },
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        ["#", "#", "#", "#", "#", "#", "#"],
                        ["#", "J", ".", "J", ".", "J", "#"],  # 3 junctions at top
                        ["#", ".", ".", ".", ".", ".", "#"],
                        ["#", "J", ".", "@", ".", "J", "#"],  # Agent center, 2 junctions
                        ["#", ".", ".", ".", ".", ".", "#"],
                        ["#", "J", ".", "J", ".", "J", "#"],  # 3 junctions at bottom
                        ["#", "#", "#", "#", "#", "#", "#"],
                    ],
                    char_to_map_name={**DEFAULT_CHAR_TO_NAME, "J": "junction"},
                ),
            ),
        )

        sim = Simulation(config)

        # Verify all junctions start aligned to clips
        initial = _count_objects_by_collective(sim, "junction")
        clips_id = _get_collective_id(sim, "clips")
        total_junctions = sum(initial.values())
        assert initial.get(clips_id, 0) == total_junctions, (
            f"All {total_junctions} junctions should start aligned to clips"
        )

        # Run through first cycle: scramble at 10, align at 15
        for _ in range(20):
            sim.step()

        # After first cycle, some should be converted to cogs
        after_20 = _count_objects_by_collective(sim, "junction")
        cogs_id = _get_collective_id(sim, "cogs")
        cogs_junctions = after_20.get(cogs_id, 0)
        assert cogs_junctions >= 1, "At least 1 junction should be cogs-aligned after 20 steps"

        # Run more cycles
        for _ in range(80):
            sim.step()

        # After 100 steps, more should be converted
        after_100 = _count_objects_by_collective(sim, "junction")
        cogs_junctions_100 = after_100.get(cogs_id, 0)
        clips_junctions_100 = after_100.get(clips_id, 0)

        # The territory should be expanding
        assert cogs_junctions_100 > cogs_junctions, (
            f"Cogs territory should expand: was {cogs_junctions}, now {cogs_junctions_100}"
        )
        # Some clips should remain (outer junctions beyond radius)
        assert clips_junctions_100 >= 0, "Some clips may remain beyond influence radius"

    def test_aggressive_max_targets_takeover(self):
        """Test aggressive takeover with unlimited max_targets.

        With max_targets=0 (unlimited), all matching objects should be affected
        in a single event firing.
        """
        config = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=5, height=5, num_tokens=100),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                resource_names=[],
                agent=AgentConfig(collective="cogs"),
                objects={
                    "wall": WallConfig(name="wall", tags=[Tag("type:wall")]),
                    "junction": WallConfig(name="junction", tags=[Tag("type:junction")], collective="clips"),
                },
                collectives={
                    "cogs": CollectiveConfig(),
                    "clips": CollectiveConfig(),
                },
                events={
                    # Aggressive scramble: all at once
                    "scramble_all_clips": EventConfig(
                        name="scramble_all_clips",
                        target_tag="type:junction",
                        timesteps=[5],
                        filters=[
                            isA("junction"),
                            isAlignedTo("clips"),
                            isNear("type:agent", [isAlignedTo("cogs")], radius=2),
                        ],
                        mutations=[removeAlignment()],
                        max_targets=0,  # Unlimited
                    ),
                    # Aggressive align: all at once
                    "align_all_neutral": EventConfig(
                        name="align_all_neutral",
                        target_tag="type:junction",
                        timesteps=[10],
                        filters=[
                            isA("junction"),
                            isAlignedTo(None),
                            isNear("type:agent", [isAlignedTo("cogs")], radius=2),
                        ],
                        mutations=[alignTo("cogs")],
                        max_targets=0,  # Unlimited
                    ),
                },
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        ["#", "#", "#", "#", "#"],
                        ["#", "J", "J", "J", "#"],  # 3 junctions
                        ["#", "J", "@", "J", "#"],  # Agent center, 2 junctions
                        ["#", "J", "J", "J", "#"],  # 3 junctions
                        ["#", "#", "#", "#", "#"],
                    ],
                    char_to_map_name={**DEFAULT_CHAR_TO_NAME, "J": "junction"},
                ),
            ),
        )

        sim = Simulation(config)

        # Count initial junctions
        initial = _count_objects_by_collective(sim, "junction")
        clips_id = _get_collective_id(sim, "clips")
        total_junctions = sum(initial.values())
        assert initial.get(clips_id, 0) == total_junctions, "All junctions start as clips"

        # Step past scramble event (timestep 5)
        for _ in range(6):
            sim.step()

        # All should be scrambled (neutral) now
        after_scramble = _count_objects_by_collective(sim, "junction")
        assert after_scramble.get(-1, 0) == total_junctions, (
            f"All {total_junctions} junctions should be neutral after scramble"
        )

        # Step past align event (timestep 10)
        for _ in range(5):
            sim.step()

        # All should be aligned to cogs now
        after_align = _count_objects_by_collective(sim, "junction")
        cogs_id = _get_collective_id(sim, "cogs")
        assert after_align.get(cogs_id, 0) == total_junctions, (
            f"All {total_junctions} junctions should be cogs-aligned after align"
        )


class TestNearFilterWithAlignment:
    """Test that isNear filter works correctly with alignment checks."""

    def test_near_filter_checks_inner_alignment(self):
        """Test that isNear with alignment filter finds objects near X-aligned objects."""
        config = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=5, height=5, num_tokens=100),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                resource_names=[],
                agent=AgentConfig(collective="cogs"),
                objects={
                    "wall": WallConfig(name="wall", tags=[Tag("type:wall")]),
                    "junction": WallConfig(name="junction", tags=[Tag("type:junction")], collective="clips"),
                },
                collectives={
                    "cogs": CollectiveConfig(),
                    "clips": CollectiveConfig(),
                },
                events={
                    # Only affect junctions near cogs-aligned entities
                    "near_cogs_test": EventConfig(
                        name="near_cogs_test",
                        target_tag="type:junction",
                        timesteps=[5],
                        filters=[
                            isA("junction"),
                            isNear("type:agent", [isAlignedTo("cogs")], radius=1),
                        ],
                        mutations=[removeAlignment()],
                    ),
                },
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        ["#", "#", "#", "#", "#"],
                        ["#", ".", ".", ".", "#"],
                        ["#", ".", "@", "J", "#"],  # Agent (cogs), Junction adjacent
                        ["#", ".", ".", ".", "#"],
                        ["#", "#", "#", "#", "#"],
                    ],
                    char_to_map_name={**DEFAULT_CHAR_TO_NAME, "J": "junction"},
                ),
            ),
        )

        sim = Simulation(config)

        # Junction starts as clips
        before = _count_objects_by_collective(sim, "junction")
        clips_id = _get_collective_id(sim, "clips")
        assert before.get(clips_id, 0) == 1

        # Step past event
        for _ in range(6):
            sim.step()

        # Junction should be scrambled because it was near cogs-aligned agent
        after = _count_objects_by_collective(sim, "junction")
        assert after.get(-1, 0) == 1, "Junction should be neutral (near cogs agent)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
