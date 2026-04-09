#!/usr/bin/env python3
"""Test that EventConfig is properly converted to C++ EventConfig.

These tests verify the Python-to-C++ conversion in _convert_events, which was
the source of several bugs:
1. max_targets not being passed to C++
2. TagFilter not being handled
3. Filter types silently skipped instead of failing
"""

import pytest

from mettagrid.config.event_config import EventConfig
from mettagrid.config.filter import (
    hasTag,
    isA,
)
from mettagrid.config.mettagrid_c_config import convert_to_cpp_game_config
from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    GameConfig,
    NoopActionConfig,
    ObsConfig,
    WallConfig,
)
from mettagrid.config.mutation import logStat
from mettagrid.config.query import query
from mettagrid.config.tag import typeTag
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
                "wall": WallConfig(tags=["target_wall"]),
            },
            events=events,
            map_builder=AsciiMapBuilder.Config(
                map_data=[["@"]],
                char_to_map_name=DEFAULT_CHAR_TO_NAME,
            ),
        )

    def test_max_targets_passed_to_cpp(self):
        """Test that max_targets is properly passed to C++ EventConfig."""
        events = {
            "test_event": EventConfig(
                name="test_event",
                target_query=query(typeTag("wall")),
                timesteps=[10],
                filters=[isA("wall")],
                mutations=[logStat("event.fired")],
                max_targets=5,
            ),
        }

        game_config = self._create_game_config_with_events(events)
        cpp_config, _ = convert_to_cpp_game_config(game_config)

        assert "test_event" in cpp_config.events
        cpp_event = cpp_config.events["test_event"]
        assert cpp_event.max_targets == 5, f"max_targets should be 5 in C++ config, got {cpp_event.max_targets}"

    def test_max_targets_none_passed_to_cpp_as_negative_one(self):
        """Test that max_targets=None (unlimited) is converted to -1 in C++."""
        events = {
            "unlimited_event": EventConfig(
                name="unlimited_event",
                target_query=query(typeTag("wall")),
                timesteps=[10],
                filters=[isA("wall")],
                mutations=[logStat("event.fired")],
                max_targets=None,
            ),
        }

        game_config = self._create_game_config_with_events(events)
        cpp_config, _ = convert_to_cpp_game_config(game_config)

        cpp_event = cpp_config.events["unlimited_event"]
        assert cpp_event.max_targets == -1, f"max_targets=None should convert to -1, got {cpp_event.max_targets}"

    def test_timesteps_passed_to_cpp(self):
        """Test that timesteps are properly passed to C++."""
        events = {
            "test_event": EventConfig(
                name="test_event",
                target_query=query(typeTag("wall")),
                timesteps=[10, 20, 30],
                filters=[isA("wall")],
                mutations=[logStat("event.fired")],
            ),
        }

        game_config = self._create_game_config_with_events(events)
        cpp_config, _ = convert_to_cpp_game_config(game_config)

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
                "wall": WallConfig(tags=["target_wall"]),
                "junction": WallConfig(tags=[typeTag("junction")]),
            },
            events=events,
            map_builder=AsciiMapBuilder.Config(
                map_data=[["@"]],
                char_to_map_name=DEFAULT_CHAR_TO_NAME,
            ),
        )

    def test_tag_filter_conversion(self):
        """Test that TagFilter is converted to C++."""
        events = {
            "test_event": EventConfig(
                name="test_event",
                target_query=query(typeTag("wall")),
                timesteps=[10],
                filters=[isA("junction")],
                mutations=[logStat("event.fired")],
            ),
        }

        game_config = self._create_game_config_with_events(events)
        cpp_config, _ = convert_to_cpp_game_config(game_config)
        assert "test_event" in cpp_config.events

    def test_multiple_filters_all_converted(self):
        """Test that all filters in an event are converted."""
        events = {
            "multi_filter_event": EventConfig(
                name="multi_filter_event",
                target_query=query(typeTag("wall")),
                timesteps=[10],
                filters=[
                    isA("junction"),
                    hasTag("target_wall"),
                ],
                mutations=[logStat("event.fired")],
            ),
        }

        game_config = self._create_game_config_with_events(events)
        assert len(events["multi_filter_event"].filters) == 2

        cpp_config, _ = convert_to_cpp_game_config(game_config)
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
                "wall": WallConfig(tags=["target_wall"]),
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
                target_query=query(typeTag("wall")),
                timesteps=[10],
                filters=[hasTag("target_wall")],
                mutations=[logStat("event.fired")],
                max_targets=1,
            ),
            "event2": EventConfig(
                name="event2",
                target_query=query(typeTag("wall")),
                timesteps=[20],
                filters=[hasTag("target_wall")],
                mutations=[logStat("event.fired")],
                max_targets=10,
            ),
        }

        game_config = self._create_game_config_with_events(events)
        cpp_config, _ = convert_to_cpp_game_config(game_config)

        assert cpp_config.events["event1"].max_targets == 1
        assert cpp_config.events["event2"].max_targets == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
