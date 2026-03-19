#!/usr/bin/env python3

"""Test event configuration classes and helper functions."""

from mettagrid.config.event_config import EventConfig, once, periodic
from mettagrid.config.filter import (
    MaxDistanceFilter,
    OrFilter,
    Query,
    ResourceFilter,
    TagFilter,
    TagPrefixFilter,
    VibeFilter,
    actorVibe,
    anyOf,
    hasTag,
    hasTagPrefix,
    isA,
    isNear,
    query,
    targetHas,
)
from mettagrid.config.filter.filter import HandlerTarget
from mettagrid.config.game_value import SumGameValue, stat, val
from mettagrid.config.mettagrid_config import (
    GameConfig,
    MettaGridConfig,
)
from mettagrid.config.mutation import (
    StatsMutation,
    logStat,
)
from mettagrid.config.tag import typeTag


class TestPeriodicHelper:
    """Tests for the periodic() helper function."""

    def test_periodic_basic(self):
        """Test basic periodic timestep generation."""
        result = periodic(start=100, period=50, end=300)
        assert result == [100, 150, 200, 250, 300]

    def test_periodic_no_end(self):
        """Test periodic without explicit end defaults to 100000."""
        result = periodic(start=0, period=10000)
        # Should generate: 0, 10000, 20000, ..., 100000
        assert result[0] == 0
        assert result[-1] == 100000
        assert len(result) == 11

    def test_periodic_single_step(self):
        """Test periodic with period larger than range."""
        result = periodic(start=50, period=100, end=50)
        assert result == [50]


class TestOnceHelper:
    """Tests for the once() helper function."""

    def test_once_basic(self):
        """Test once returns single-element list."""
        result = once(500)
        assert result == [500]


class TestTagFilter:
    """Tests for TagFilter configuration."""

    def test_tag_filter_creation(self):
        """Test creating TagFilter directly."""
        f = TagFilter(target=HandlerTarget.TARGET, tag=typeTag("hub"))
        assert f.filter_type == "tag"
        assert f.tag == typeTag("hub")

    def test_has_tag_helper(self):
        """Test hasTag helper function."""
        f = hasTag(typeTag("junction"))
        assert isinstance(f, TagFilter)
        assert f.filter_type == "tag"
        assert f.tag == typeTag("junction")

    def test_tag_filter_serialization(self):
        """Test TagFilter serialization."""
        f = TagFilter(target=HandlerTarget.TARGET, tag=typeTag("battery_station"))
        data = f.model_dump()
        assert data["filter_type"] == "tag"
        assert data["tag"] == typeTag("battery_station")


class TestMaxDistanceFilter:
    """Tests for MaxDistanceFilter configuration."""

    def test_max_distance_filter_creation(self):
        """Test creating MaxDistanceFilter via isNear helper."""
        f = isNear(query("junction", [hasTag("team:clips")]), radius=2)
        assert f.filter_type == "max_distance"
        assert f.query.source == "junction"
        assert len(f.query.filters) == 1
        assert f.radius == 2

    def test_is_near_helper(self):
        """Test isNear helper function."""
        f = isNear(query("hub", [hasTag("team:cogs")]), radius=3)
        assert isinstance(f, MaxDistanceFilter)
        assert f.filter_type == "max_distance"
        assert f.query.source == "hub"
        assert len(f.query.filters) == 1
        assert f.radius == 3

    def test_max_distance_filter_default_radius(self):
        """Test isNear with default radius."""
        f = isNear(query("wall", [hasTag("team:a")]))
        assert f.radius == 1
        assert f.query.source == "wall"

    def test_max_distance_filter_wraps_string_query(self):
        f = isNear("hub", radius=2)
        assert isinstance(f.query, Query)
        assert f.query.source == "hub"

    def test_max_distance_filter_serialization(self):
        """Test MaxDistanceFilter serialization."""
        f = isNear(query("chest", [hasTag("team:a")]), radius=2)
        data = f.model_dump()
        assert data["filter_type"] == "max_distance"
        assert data["query"]["source"] == "chest"
        assert len(data["query"]["filters"]) == 1
        assert data["radius"] == 2


class TestStatsMutation:
    """Tests for StatsMutation configuration."""

    def test_stats_mutation_creation(self):
        """Test creating StatsMutation directly."""
        m = StatsMutation(stat="event.boundary_crossed", source=val(1))
        assert m.mutation_type == "stats"
        assert m.stat == "event.boundary_crossed"
        assert m.source == val(1)

    def test_stats_mutation_with_sum_source(self):
        """Test StatsMutation with SumGameValue source."""
        m = StatsMutation(stat="custom.metric", source=SumGameValue(values=[stat("game.custom.metric"), val(0)]))
        assert m.target.value == "game"

    def test_log_stat_helper(self):
        """Test logStat helper function."""
        m = logStat(stat="event.test")
        assert isinstance(m, StatsMutation)
        assert m.mutation_type == "stats"
        assert m.stat == "event.test"
        assert m.source == SumGameValue(values=[stat("game.event.test"), val(1)])

    def test_log_stat_helper_with_delta(self):
        """Test logStat helper function with custom delta."""
        m = logStat(stat="event.damage", delta=5)
        assert m.stat == "event.damage"
        assert m.source == SumGameValue(values=[stat("game.event.damage"), val(5)])

    def test_stats_mutation_serialization(self):
        """Test StatsMutation serialization."""
        m = StatsMutation(stat="event.test", source=val(3))
        data = m.model_dump()
        assert data["mutation_type"] == "stats"
        assert data["stat"] == "event.test"


class TestEventConfig:
    """Tests for EventConfig configuration."""

    def test_event_config_creation(self):
        """Test creating EventConfig."""
        event = EventConfig(
            name="test_event",
            target_query=query(typeTag("wall")),
            timesteps=[100, 200, 300],
            filters=[hasTag(typeTag("junction"))],
            mutations=[logStat("event.test")],
        )
        assert event.name == "test_event"
        assert event.timesteps == [100, 200, 300]
        assert len(event.filters) == 1
        assert len(event.mutations) == 1

    def test_event_config_with_periodic(self):
        """Test EventConfig with periodic timesteps."""
        event = EventConfig(
            name="periodic_event",
            target_query=query(typeTag("wall")),
            timesteps=periodic(start=0, period=100, end=500),
            filters=[hasTag("agent")],
            mutations=[logStat("event.periodic")],
        )
        assert event.timesteps == [0, 100, 200, 300, 400, 500]

    def test_event_config_with_once(self):
        """Test EventConfig with once timestep."""
        event = EventConfig(
            name="one_time_event",
            target_query=query(typeTag("wall")),
            timesteps=once(1000),
            filters=[hasTag("agent")],
            mutations=[logStat("event.triggered")],
        )
        assert event.timesteps == [1000]

    def test_event_config_serialization(self):
        """Test EventConfig serialization."""
        event = EventConfig(
            name="proximity_event",
            target_query=query(typeTag("wall")),
            timesteps=[50, 100],
            filters=[hasTag("agent"), isNear(query("agent", [hasTag("team:cogs")]), radius=2)],
            mutations=[logStat(stat="proximity.touched")],
        )
        data = event.model_dump()
        assert data["name"] == "proximity_event"
        assert data["timesteps"] == [50, 100]
        assert len(data["filters"]) == 2
        assert data["filters"][0]["filter_type"] == "tag"
        assert data["filters"][1]["filter_type"] == "max_distance"
        assert len(data["mutations"]) == 1
        assert data["mutations"][0]["mutation_type"] == "stats"

    def test_event_config_deserialization(self):
        """Test EventConfig deserialization."""
        event = EventConfig(
            name="test",
            target_query=query(typeTag("wall")),
            timesteps=[100],
            filters=[hasTag(typeTag("agent"))],
            mutations=[logStat("test.stat")],
        )
        json_str = event.model_dump_json()
        restored = EventConfig.model_validate_json(json_str)
        assert restored.name == "test"
        assert restored.timesteps == [100]
        assert len(restored.filters) == 1
        assert len(restored.mutations) == 1


class TestEventsInGameConfig:
    """Tests for events integration in GameConfig."""

    def test_game_config_with_events(self):
        """Test GameConfig with events field."""
        config = GameConfig(
            num_agents=4,
            events={
                "periodic_stat": EventConfig(
                    name="periodic_stat",
                    target_query=query(typeTag("wall")),
                    timesteps=periodic(0, 100, 500),
                    filters=[hasTag("agent")],
                    mutations=[logStat("tick.marker")],
                ),
                "proximity_check": EventConfig(
                    name="proximity_check",
                    target_query=query(typeTag("wall")),
                    timesteps=once(250),
                    filters=[isA("hub"), isNear(query("hub", [hasTag("team:a")]), radius=2)],
                    mutations=[logStat("proximity.check")],
                ),
            },
        )
        assert len(config.events) == 2
        assert config.events["periodic_stat"].name == "periodic_stat"
        assert config.events["proximity_check"].name == "proximity_check"

    def test_game_config_events_serialization(self):
        """Test GameConfig events serialization."""
        config = GameConfig(
            num_agents=2,
            events={
                "test_event": EventConfig(
                    name="test_event",
                    target_query=query(typeTag("wall")),
                    timesteps=[100],
                    filters=[hasTag(typeTag("junction"))],
                    mutations=[logStat("event.test")],
                )
            },
        )
        data = config.model_dump()
        assert "events" in data
        assert len(data["events"]) == 1
        assert data["events"]["test_event"]["name"] == "test_event"

    def test_metta_grid_config_with_events(self):
        """Test MettaGridConfig with events."""
        config = MettaGridConfig.EmptyRoom(num_agents=4)
        config.game.events = {
            "room_event": EventConfig(
                name="room_event",
                target_query=query(typeTag("wall")),
                timesteps=once(500),
                filters=[hasTag("agent")],
                mutations=[logStat("event.room")],
            )
        }
        # Serialize and deserialize
        json_str = config.model_dump_json()
        restored = MettaGridConfig.model_validate_json(json_str)
        assert len(restored.game.events) == 1
        assert restored.game.events["room_event"].name == "room_event"


class TestFilterPolymorphism:
    """Tests for filter type polymorphism in events."""

    def test_mixed_filters_serialization(self):
        """Test serialization of events with mixed filter types."""
        event = EventConfig(
            name="mixed_filters",
            target_query=query(typeTag("wall")),
            timesteps=[100],
            filters=[
                hasTag(typeTag("junction")),
                isNear(query("junction", [hasTag("team:b")]), radius=2),
            ],
            mutations=[],
        )
        data = event.model_dump()
        assert len(data["filters"]) == 2
        assert data["filters"][0]["filter_type"] == "tag"
        assert data["filters"][1]["filter_type"] == "max_distance"

    def test_mixed_filters_deserialization(self):
        """Test deserialization restores correct filter types."""
        event = EventConfig(
            name="mixed_filters",
            target_query=query(typeTag("wall")),
            timesteps=[100],
            filters=[
                hasTag(typeTag("junction")),
                isNear(query("junction", [hasTag("team:a")])),
            ],
            mutations=[],
        )
        json_str = event.model_dump_json()
        restored = EventConfig.model_validate_json(json_str)
        assert len(restored.filters) == 2
        assert isinstance(restored.filters[0], TagFilter)
        assert isinstance(restored.filters[1], MaxDistanceFilter)

    def test_nested_or_filter_deserialization(self):
        event = EventConfig(
            name="nested_or",
            target_query=query(typeTag("wall")),
            timesteps=[100],
            filters=[anyOf([actorVibe("up"), targetHas({"gold": 1}), hasTagPrefix("team")])],
            mutations=[],
        )
        restored = EventConfig.model_validate_json(event.model_dump_json())
        assert isinstance(restored.filters[0], OrFilter)
        assert isinstance(restored.filters[0].inner[0], VibeFilter)
        assert isinstance(restored.filters[0].inner[1], ResourceFilter)
        assert isinstance(restored.filters[0].inner[2], TagPrefixFilter)


class TestMutationPolymorphism:
    """Tests for mutation type polymorphism in events."""

    def test_stats_mutations_serialization(self):
        """Test serialization of events with stats mutations."""
        event = EventConfig(
            name="stats_mutations",
            target_query=query(typeTag("wall")),
            timesteps=[100],
            filters=[hasTag("agent")],
            mutations=[
                logStat(stat="event.test", delta=5),
            ],
        )
        data = event.model_dump()
        assert len(data["mutations"]) == 1
        assert data["mutations"][0]["mutation_type"] == "stats"

    def test_stats_mutations_deserialization(self):
        """Test deserialization restores correct mutation types."""
        event = EventConfig(
            name="stats_mutations",
            target_query=query(typeTag("wall")),
            timesteps=[100],
            filters=[hasTag("agent")],
            mutations=[
                logStat(stat="event.test", delta=5),
            ],
        )
        json_str = event.model_dump_json()
        restored = EventConfig.model_validate_json(json_str)
        assert len(restored.mutations) == 1
        assert isinstance(restored.mutations[0], StatsMutation)
        assert restored.mutations[0].source == SumGameValue(values=[stat("game.event.test"), val(5)])


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
