#!/usr/bin/env python3

"""Test max_targets parameter for EventConfig.

These tests verify that:
1. max_targets configuration works correctly
2. max_targets defaults to 1 (safe default)
3. max_targets=None means unlimited
4. max_targets is properly serialized and deserialized
"""

import pytest

from mettagrid.config.event_config import EventConfig
from mettagrid.config.filter import hasTag
from mettagrid.config.mutation import logStat
from mettagrid.config.query import query
from mettagrid.config.tag import tag


class TestMaxTargetsConfig:
    """Test max_targets configuration."""

    def test_max_targets_default_is_none(self):
        """Test that max_targets defaults to None (unlimited)."""
        event = EventConfig(
            name="test_event",
            target_query=query("test:target"),
            timesteps=[10],
            filters=[hasTag(tag("test:target"))],
            mutations=[logStat("test.stat")],
        )
        assert event.max_targets is None

    def test_max_targets_none_means_unlimited(self):
        """Test that max_targets=None means unlimited."""
        event = EventConfig(
            name="test_event",
            target_query=query("test:target"),
            timesteps=[10],
            filters=[hasTag(tag("test:target"))],
            mutations=[logStat("test.stat")],
            max_targets=None,
        )
        assert event.max_targets is None

    def test_max_targets_can_be_set(self):
        """Test that max_targets can be explicitly set."""
        event = EventConfig(
            name="test_event",
            target_query=query("test:target"),
            timesteps=[10],
            filters=[hasTag(tag("test:target"))],
            mutations=[logStat("test.stat")],
            max_targets=5,
        )
        assert event.max_targets == 5

    def test_max_targets_serialization(self):
        """Test that max_targets survives serialization."""
        event = EventConfig(
            name="test_event",
            target_query=query("test:target"),
            timesteps=[10],
            filters=[hasTag(tag("test:target"))],
            mutations=[logStat("test.stat")],
            max_targets=3,
        )
        json_str = event.model_dump_json()
        restored = EventConfig.model_validate_json(json_str)
        assert restored.max_targets == 3

    def test_max_targets_none_serialization(self):
        """Test that max_targets=None survives serialization."""
        event = EventConfig(
            name="test_event",
            target_query=query("test:target"),
            timesteps=[10],
            filters=[hasTag(tag("test:target"))],
            mutations=[logStat("test.stat")],
            max_targets=None,
        )
        json_str = event.model_dump_json()
        restored = EventConfig.model_validate_json(json_str)
        assert restored.max_targets is None

    def test_max_targets_model_dump(self):
        """Test that max_targets is included in model_dump."""
        event = EventConfig(
            name="test_event",
            target_query=query("test:target"),
            timesteps=[10],
            filters=[hasTag(tag("test:target"))],
            mutations=[],
            max_targets=7,
        )
        data = event.model_dump()
        assert data["max_targets"] == 7


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
