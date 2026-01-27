"""Tests for event validation."""

from mettagrid.config.event_config import EventConfig, periodic
from mettagrid.config.filter import hasTag
from mettagrid.config.mutation import logStat
from mettagrid.config.tag import Tag


class TestEventValidation:
    def test_event_with_tag_filter_passes(self):
        """Event with TagFilter should pass validation."""
        event = EventConfig(
            name="valid_event",
            target_tag="target_tag",
            timesteps=periodic(start=1, period=10, end=100),
            filters=[hasTag(Tag("target_tag"))],
            mutations=[logStat(stat="test")],
        )
        assert event.name == "valid_event"
        assert len(event.filters) == 1

    def test_event_without_filters_accepted(self):
        """Event without filters is currently allowed (validation not enforced)."""
        # Note: This is allowed at the config level but events without
        # TagFilter won't be efficient at runtime since they won't use
        # the tag index for pre-filtering.
        event = EventConfig(
            name="no_filter_event",
            target_tag="target_tag",
            timesteps=periodic(start=1, period=10, end=100),
            filters=[],
            mutations=[logStat(stat="test")],
        )
        assert event.name == "no_filter_event"
        assert len(event.filters) == 0
