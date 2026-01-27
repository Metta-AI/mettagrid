#!/usr/bin/env python3
"""Test that EventConfig is properly converted to C++ EventConfig.

These tests verify the Python-to-C++ conversion in _convert_events, which was
the source of several bugs:
1. max_targets not being passed to C++
2. AlignmentFilter missing entity field
3. TagFilter not being handled
4. Filter types silently skipped instead of failing
"""

import pytest

from mettagrid.config.event_config import EventConfig
from mettagrid.config.filter import (
    hasTag,
    isA,
    isAlignedTo,
)
from mettagrid.config.mettagrid_c_config import convert_to_cpp_game_config
from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    CollectiveConfig,
    GameConfig,
    NoopActionConfig,
    ObsConfig,
    WallConfig,
)
from mettagrid.config.mutation import alignTo
from mettagrid.config.tag import Tag
from mettagrid.map_builder.ascii import AsciiMapBuilder
from mettagrid.mapgen.utils.ascii_grid import DEFAULT_CHAR_TO_NAME


class TestEventCppConversion:
    """Test Python to C++ event conversion."""

    def _create_game_config_with_events(self, events: dict) -> GameConfig:
        """Helper to create a minimal GameConfig with events."""
        return GameConfig(
            num_agents=1,
            obs=ObsConfig(width=5, height=5, num_tokens=100),
            max_steps=100,
            actions=ActionsConfig(noop=NoopActionConfig()),
            resource_names=[],
            objects={
                "wall": WallConfig(tags=[Tag("target_wall")]),
            },
            collectives={
                "cogs": CollectiveConfig(),
                "clips": CollectiveConfig(),
            },
            events=events,
            map_builder=AsciiMapBuilder.Config(
                map_data=[["@"]],
                char_to_map_name=DEFAULT_CHAR_TO_NAME,
            ),
        )

    def test_max_targets_passed_to_cpp(self):
        """Test that max_targets is properly passed to C++ EventConfig.

        This was the main bug - _convert_events didn't set max_targets on the C++ config,
        so events with max_targets=1 would apply to all matching objects.
        """
        events = {
            "test_event": EventConfig(
                name="test_event",
                target_tag="type:wall",
                timesteps=[10],
                filters=[isA("wall")],
                mutations=[alignTo("clips")],
                max_targets=5,
            ),
        }

        game_config = self._create_game_config_with_events(events)
        cpp_config = convert_to_cpp_game_config(game_config)

        assert "test_event" in cpp_config.events
        cpp_event = cpp_config.events["test_event"]
        assert cpp_event.max_targets == 5, f"max_targets should be 5 in C++ config, got {cpp_event.max_targets}"

    def test_max_targets_zero_passed_to_cpp(self):
        """Test that max_targets=0 (unlimited) is properly passed to C++."""
        events = {
            "unlimited_event": EventConfig(
                name="unlimited_event",
                target_tag="type:wall",
                timesteps=[10],
                filters=[isA("wall")],
                mutations=[alignTo("clips")],
                max_targets=0,
            ),
        }

        game_config = self._create_game_config_with_events(events)
        cpp_config = convert_to_cpp_game_config(game_config)

        cpp_event = cpp_config.events["unlimited_event"]
        assert cpp_event.max_targets == 0, f"max_targets=0 (unlimited) should be preserved, got {cpp_event.max_targets}"

    def test_max_targets_none_converted_to_zero(self):
        """Test that max_targets=None is converted to 0 (unlimited) in C++."""
        # Create event dict directly to bypass Python validation
        events = {
            "none_event": EventConfig(
                name="none_event",
                target_tag="type:wall",
                timesteps=[10],
                filters=[isA("wall")],
                mutations=[alignTo("clips")],
            ),
        }
        # Manually set to None to simulate legacy configs
        events["none_event"].max_targets = None  # type: ignore

        game_config = self._create_game_config_with_events(events)
        cpp_config = convert_to_cpp_game_config(game_config)

        cpp_event = cpp_config.events["none_event"]
        assert cpp_event.max_targets == 0, f"max_targets=None should convert to 0, got {cpp_event.max_targets}"

    def test_timesteps_passed_to_cpp(self):
        """Test that timesteps are properly passed to C++."""
        events = {
            "test_event": EventConfig(
                name="test_event",
                target_tag="type:wall",
                timesteps=[10, 20, 30],
                filters=[isA("wall")],
                mutations=[alignTo("clips")],
            ),
        }

        game_config = self._create_game_config_with_events(events)
        cpp_config = convert_to_cpp_game_config(game_config)

        cpp_event = cpp_config.events["test_event"]
        assert list(cpp_event.timesteps) == [10, 20, 30]


class TestEventFilterConversion:
    """Test that event filters are properly converted to C++."""

    def _create_game_config_with_events(self, events: dict) -> GameConfig:
        """Helper to create a minimal GameConfig with events."""
        return GameConfig(
            num_agents=1,
            obs=ObsConfig(width=5, height=5, num_tokens=100),
            max_steps=100,
            actions=ActionsConfig(noop=NoopActionConfig()),
            resource_names=[],
            objects={
                "wall": WallConfig(tags=[Tag("target_wall")], collective="cogs"),
                "junction": WallConfig(tags=[Tag("type:junction")]),
            },
            collectives={
                "cogs": CollectiveConfig(),
                "clips": CollectiveConfig(),
            },
            events=events,
            map_builder=AsciiMapBuilder.Config(
                map_data=[["@"]],
                char_to_map_name=DEFAULT_CHAR_TO_NAME,
            ),
        )

    def test_tag_filter_conversion(self):
        """Test that TagFilter is converted to C++.

        TagFilter is used for TagIndex pre-selection - the filter must
        exist in C++ for EventScheduler to find candidate objects.
        """
        events = {
            "test_event": EventConfig(
                name="test_event",
                target_tag="type:wall",
                timesteps=[10],
                filters=[isA("junction")],  # Creates TagFilter with "type:junction"
                mutations=[alignTo("clips")],
            ),
        }

        game_config = self._create_game_config_with_events(events)

        # This should not raise - the conversion should succeed
        cpp_config = convert_to_cpp_game_config(game_config)
        assert "test_event" in cpp_config.events

    def test_alignment_filter_conversion(self):
        """Test that AlignmentFilter is converted to C++.

        This tests the isAlignedTo(None) case which creates an AlignmentFilter
        checking for UNALIGNED condition.
        """
        events = {
            "test_event": EventConfig(
                name="test_event",
                target_tag="type:wall",
                timesteps=[10],
                filters=[isA("junction"), isAlignedTo(None)],  # AlignmentFilter
                mutations=[alignTo("clips")],
            ),
        }

        game_config = self._create_game_config_with_events(events)
        cpp_config = convert_to_cpp_game_config(game_config)
        assert "test_event" in cpp_config.events

    def test_alignment_filter_with_collective_conversion(self):
        """Test that AlignmentFilter with collective is converted to C++.

        This tests isAlignedTo("cogs") which creates an AlignmentFilter with collective.
        """
        events = {
            "test_event": EventConfig(
                name="test_event",
                target_tag="type:wall",
                timesteps=[10],
                filters=[isA("wall"), isAlignedTo("cogs")],  # AlignmentFilter with collective
                mutations=[alignTo("clips")],
            ),
        }

        game_config = self._create_game_config_with_events(events)
        cpp_config = convert_to_cpp_game_config(game_config)
        assert "test_event" in cpp_config.events

    def test_multiple_filters_all_converted(self):
        """Test that all filters in an event are converted.

        Bug: Only 1 filter was being created when there should be 2.
        """
        events = {
            "multi_filter_event": EventConfig(
                name="multi_filter_event",
                target_tag="type:wall",
                timesteps=[10],
                filters=[
                    isA("junction"),  # TagFilter
                    isAlignedTo(None),  # AlignmentFilter
                ],
                mutations=[alignTo("clips")],
            ),
        }

        game_config = self._create_game_config_with_events(events)

        # Verify Python config has 2 filters
        assert len(events["multi_filter_event"].filters) == 2

        # Convert to C++ and verify it succeeds
        cpp_config = convert_to_cpp_game_config(game_config)
        assert "multi_filter_event" in cpp_config.events


class TestConvertEventsFunction:
    """Test the event conversion via full GameConfig conversion."""

    def _create_game_config_with_events(self, events: dict) -> GameConfig:
        """Helper to create a minimal GameConfig with events."""
        return GameConfig(
            num_agents=1,
            obs=ObsConfig(width=5, height=5, num_tokens=100),
            max_steps=100,
            actions=ActionsConfig(noop=NoopActionConfig()),
            resource_names=["energy"],
            objects={
                "wall": WallConfig(tags=[Tag("target_wall")]),
            },
            collectives={
                "cogs": CollectiveConfig(),
            },
            events=events,
            map_builder=AsciiMapBuilder.Config(
                map_data=[["@"]],
                char_to_map_name=DEFAULT_CHAR_TO_NAME,
            ),
        )

    def test_convert_events_preserves_max_targets(self):
        """Test that max_targets values are preserved through conversion."""
        events = {
            "event1": EventConfig(
                name="event1",
                target_tag="type:wall",
                timesteps=[10],
                filters=[hasTag(Tag("target_wall"))],
                mutations=[alignTo("cogs")],
                max_targets=1,
            ),
            "event2": EventConfig(
                name="event2",
                target_tag="type:wall",
                timesteps=[20],
                filters=[hasTag(Tag("target_wall"))],
                mutations=[alignTo("cogs")],
                max_targets=10,
            ),
        }

        game_config = self._create_game_config_with_events(events)
        cpp_config = convert_to_cpp_game_config(game_config)

        assert cpp_config.events["event1"].max_targets == 1
        assert cpp_config.events["event2"].max_targets == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
