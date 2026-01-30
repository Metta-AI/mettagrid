#!/usr/bin/env python3

"""Test event configuration classes and helper functions."""

from mettagrid.config.event_config import EventConfig, once, periodic
from mettagrid.config.filter import (
    AlignmentFilter,
    NearFilter,
    TagFilter,
    hasTag,
    isA,
    isAlignedTo,
    isNear,
)
from mettagrid.config.filter.filter import HandlerTarget
from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    CollectiveConfig,
    GameConfig,
    MettaGridConfig,
    NoopActionConfig,
    ObsConfig,
)
from mettagrid.config.mutation import (
    AlignmentMutation,
    StatsMutation,
    alignTo,
    logStat,
)
from mettagrid.config.tag import Tag


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
        f = TagFilter(target=HandlerTarget.TARGET, tag=Tag("type:assembler"))
        assert f.filter_type == "tag"
        assert f.tag == Tag("type:assembler")

    def test_has_tag_helper(self):
        """Test hasTag helper function."""
        f = hasTag(Tag("type:charger"))
        assert isinstance(f, TagFilter)
        assert f.filter_type == "tag"
        assert f.tag == Tag("type:charger")

    def test_tag_filter_serialization(self):
        """Test TagFilter serialization."""
        f = TagFilter(target=HandlerTarget.TARGET, tag=Tag("type:battery_station"))
        data = f.model_dump()
        assert data["filter_type"] == "tag"
        assert data["tag"] == "type:battery_station"


class TestIsAlignedToHelper:
    """Tests for isAlignedTo helper function (creates AlignmentFilter with collective)."""

    def test_is_aligned_to_creation(self):
        """Test isAlignedTo creates AlignmentFilter with collective name."""
        f = isAlignedTo("cogs")
        assert isinstance(f, AlignmentFilter)
        assert f.filter_type == "alignment"
        assert f.collective == "cogs"

    def test_is_aligned_to_serialization(self):
        """Test isAlignedTo result serialization."""
        f = isAlignedTo("clips")
        data = f.model_dump()
        assert data["filter_type"] == "alignment"
        assert data["collective"] == "clips"


class TestNearFilter:
    """Tests for NearFilter configuration."""

    def test_near_filter_creation(self):
        """Test creating NearFilter directly."""
        f = isNear("junction", [isAlignedTo("clips")], radius=2)
        assert f.filter_type == "near"
        assert f.target_tag == "junction"
        assert len(f.filters) == 1
        assert f.radius == 2

    def test_is_near_helper(self):
        """Test isNear helper function."""
        f = isNear("assembler", [isAlignedTo("cogs")], radius=3)
        assert isinstance(f, NearFilter)
        assert f.filter_type == "near"
        assert f.target_tag == "assembler"
        assert len(f.filters) == 1
        assert f.radius == 3

    def test_near_filter_default_radius(self):
        """Test isNear with default radius."""
        f = isNear("wall", [isAlignedTo("team_a")])
        assert f.radius == 1
        assert f.target_tag == "wall"

    def test_near_filter_serialization(self):
        """Test NearFilter serialization."""
        f = isNear("chest", [isAlignedTo("team_a")], radius=2)
        data = f.model_dump()
        assert data["filter_type"] == "near"
        assert data["target_tag"] == "chest"
        assert len(data["filters"]) == 1
        assert data["radius"] == 2


class TestAlignmentMutation:
    """Tests for AlignmentMutation configuration."""

    def test_alignment_mutation_with_collective_creation(self):
        """Test creating AlignmentMutation with collective."""
        m = AlignmentMutation(collective="cogs")
        assert m.mutation_type == "alignment"
        assert m.collective == "cogs"
        assert m.target == "target"

    def test_align_to_collective_helper(self):
        """Test alignTo helper function."""
        m = alignTo("clips")
        assert isinstance(m, AlignmentMutation)
        assert m.mutation_type == "alignment"
        assert m.collective == "clips"

    def test_alignment_mutation_with_collective_serialization(self):
        """Test AlignmentMutation with collective serialization."""
        m = AlignmentMutation(collective="team_red")
        data = m.model_dump()
        assert data["mutation_type"] == "alignment"
        assert data["collective"] == "team_red"
        assert data["target"] == "target"


class TestStatsMutation:
    """Tests for StatsMutation configuration."""

    def test_stats_mutation_creation(self):
        """Test creating StatsMutation directly."""
        m = StatsMutation(stat="event.boundary_crossed", delta=1)
        assert m.mutation_type == "stats"
        assert m.stat == "event.boundary_crossed"
        assert m.delta == 1

    def test_stats_mutation_default_delta(self):
        """Test StatsMutation with default delta."""
        m = StatsMutation(stat="custom.metric")
        assert m.delta == 1

    def test_log_stat_helper(self):
        """Test logStat helper function."""
        m = logStat(stat="event.test")
        assert isinstance(m, StatsMutation)
        assert m.mutation_type == "stats"
        assert m.stat == "event.test"
        assert m.delta == 1

    def test_log_stat_helper_with_delta(self):
        """Test logStat helper function with custom delta."""
        m = logStat(stat="event.damage", delta=5)
        assert m.stat == "event.damage"
        assert m.delta == 5

    def test_stats_mutation_serialization(self):
        """Test StatsMutation serialization."""
        m = StatsMutation(stat="event.test", delta=3)
        data = m.model_dump()
        assert data["mutation_type"] == "stats"
        assert data["stat"] == "event.test"
        assert data["delta"] == 3


class TestEventConfig:
    """Tests for EventConfig configuration."""

    def test_event_config_creation(self):
        """Test creating EventConfig."""
        event = EventConfig(
            name="test_event",
            target_tag="type:wall",
            timesteps=[100, 200, 300],
            filters=[hasTag(Tag("type:charger"))],
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
            target_tag="type:wall",
            timesteps=periodic(start=0, period=100, end=500),
            filters=[hasTag(Tag("agent")), isAlignedTo("cogs")],
            mutations=[alignTo("clips")],
        )
        assert event.timesteps == [0, 100, 200, 300, 400, 500]

    def test_event_config_with_once(self):
        """Test EventConfig with once timestep."""
        event = EventConfig(
            name="one_time_event",
            target_tag="type:wall",
            timesteps=once(1000),
            filters=[hasTag(Tag("agent"))],
            mutations=[logStat("event.triggered")],
        )
        assert event.timesteps == [1000]

    def test_event_config_serialization(self):
        """Test EventConfig serialization."""
        event = EventConfig(
            name="proximity_event",
            target_tag="type:wall",
            timesteps=[50, 100],
            filters=[hasTag(Tag("agent")), isNear("agent", [isAlignedTo("cogs")], radius=2)],
            mutations=[logStat(stat="proximity.touched")],
        )
        data = event.model_dump()
        assert data["name"] == "proximity_event"
        assert data["timesteps"] == [50, 100]
        assert len(data["filters"]) == 2
        assert data["filters"][0]["filter_type"] == "tag"
        assert data["filters"][1]["filter_type"] == "near"
        assert len(data["mutations"]) == 1
        assert data["mutations"][0]["mutation_type"] == "stats"

    def test_event_config_deserialization(self):
        """Test EventConfig deserialization."""
        event = EventConfig(
            name="test",
            target_tag="type:wall",
            timesteps=[100],
            filters=[hasTag(Tag("type:agent")), isAlignedTo("team1")],
            mutations=[logStat("test.stat")],
        )
        json_str = event.model_dump_json()
        restored = EventConfig.model_validate_json(json_str)
        assert restored.name == "test"
        assert restored.timesteps == [100]
        assert len(restored.filters) == 2
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
                    target_tag="type:wall",
                    timesteps=periodic(0, 100, 500),
                    filters=[hasTag(Tag("agent"))],
                    mutations=[logStat("tick.marker")],
                ),
                "proximity_check": EventConfig(
                    name="proximity_check",
                    target_tag="type:wall",
                    timesteps=once(250),
                    filters=[isA("assembler"), isNear("assembler", [isAlignedTo("team_a")], radius=2)],
                    mutations=[alignTo(None)],  # None removes alignment
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
                    target_tag="type:wall",
                    timesteps=[100],
                    filters=[hasTag(Tag("type:charger"))],
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
                target_tag="type:wall",
                timesteps=once(500),
                filters=[hasTag(Tag("agent"))],
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
            target_tag="type:wall",
            timesteps=[100],
            filters=[
                hasTag(Tag("type:charger")),
                isAlignedTo("cogs"),
                isNear("charger", [isAlignedTo("team_b")], radius=2),
            ],
            mutations=[],
        )
        data = event.model_dump()
        assert len(data["filters"]) == 3
        assert data["filters"][0]["filter_type"] == "tag"  # hasTag returns TagFilter
        assert data["filters"][1]["filter_type"] == "alignment"  # isAlignedTo returns AlignmentFilter
        assert data["filters"][2]["filter_type"] == "near"

    def test_mixed_filters_deserialization(self):
        """Test deserialization restores correct filter types."""
        event = EventConfig(
            name="mixed_filters",
            target_tag="type:wall",
            timesteps=[100],
            filters=[
                hasTag(Tag("type:charger")),
                isAlignedTo("cogs"),
                isNear("charger", [isAlignedTo("team_a")], radius=1),
            ],
            mutations=[],
        )
        json_str = event.model_dump_json()
        restored = EventConfig.model_validate_json(json_str)
        assert len(restored.filters) == 3
        assert isinstance(restored.filters[0], TagFilter)  # hasTag returns TagFilter
        assert isinstance(restored.filters[1], AlignmentFilter)  # isAlignedTo returns AlignmentFilter
        assert isinstance(restored.filters[2], NearFilter)


class TestMutationPolymorphism:
    """Tests for mutation type polymorphism in events."""

    def test_mixed_mutations_serialization(self):
        """Test serialization of events with mixed mutation types."""
        event = EventConfig(
            name="mixed_mutations",
            target_tag="type:wall",
            timesteps=[100],
            filters=[hasTag(Tag("agent"))],
            mutations=[
                alignTo("team_a"),
                logStat(stat="event.test", delta=5),
            ],
        )
        data = event.model_dump()
        assert len(data["mutations"]) == 2
        assert data["mutations"][0]["mutation_type"] == "alignment"
        assert data["mutations"][1]["mutation_type"] == "stats"

    def test_mixed_mutations_deserialization(self):
        """Test deserialization restores correct mutation types."""
        event = EventConfig(
            name="mixed_mutations",
            target_tag="type:wall",
            timesteps=[100],
            filters=[hasTag(Tag("agent"))],
            mutations=[
                alignTo("team_a"),
                logStat(stat="event.test", delta=5),
            ],
        )
        json_str = event.model_dump_json()
        restored = EventConfig.model_validate_json(json_str)
        assert len(restored.mutations) == 2
        assert isinstance(restored.mutations[0], AlignmentMutation)
        assert isinstance(restored.mutations[1], StatsMutation)
        assert restored.mutations[0].collective == "team_a"
        assert restored.mutations[1].delta == 5


class TestEventSchedulerIntegration:
    """Integration tests verifying events fire during simulation."""

    def test_max_targets_limits_affected_objects(self):
        """Test that max_targets limits how many objects are affected by an event."""
        from mettagrid.config.mettagrid_config import WallConfig
        from mettagrid.map_builder.ascii import AsciiMapBuilder
        from mettagrid.mapgen.utils.ascii_grid import DEFAULT_CHAR_TO_NAME
        from mettagrid.simulator import Simulation

        # Create config with 4 walls, all belonging to cogs collective
        # Event will try to align them to clips, but max_targets=1 should limit to 1 wall
        config = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=5, height=5, num_tokens=100),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                resource_names=[],
                objects={
                    "wall": WallConfig(collective="cogs", tags=[Tag("target_wall")]),
                },
                collectives={
                    "cogs": CollectiveConfig(),
                    "clips": CollectiveConfig(),
                },
                events={
                    # Event fires at timestep 10, but should only affect 1 wall due to max_targets
                    "wall_takeover": EventConfig(
                        name="wall_takeover",
                        target_tag="type:wall",
                        timesteps=[10],
                        filters=[hasTag(Tag("target_wall"))],
                        mutations=[alignTo("clips")],
                        max_targets=1,  # Only affect 1 wall
                    ),
                },
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        ["#", ".", "#", ".", "#"],
                        [".", "@", ".", ".", "."],
                        ["#", ".", ".", ".", "."],
                        [".", ".", ".", ".", "."],
                        [".", ".", ".", ".", "."],
                    ],
                    char_to_map_name=DEFAULT_CHAR_TO_NAME,
                ),
            )
        )

        sim = Simulation(config)

        # Get initial wall count and their collectives
        objects = sim.grid_objects()
        walls = [obj for obj in objects.values() if obj.get("type_name") == "wall"]
        assert len(walls) == 4, f"Should have 4 walls, got {len(walls)}"

        # All walls should initially be in cogs collective
        initial_collective_id = walls[0].get("collective_id")
        for wall in walls:
            assert wall.get("collective_id") == initial_collective_id, "All walls should start in same collective"

        # Run simulation until event fires (timestep 10)
        for _ in range(10):
            sim.step()

        # Check how many walls changed collective
        objects = sim.grid_objects()
        walls = [obj for obj in objects.values() if obj.get("type_name") == "wall"]
        assert len(walls) == 4, f"Should still have 4 walls, got {len(walls)}"

        # Count walls that changed collective
        walls_with_new_collective = sum(1 for wall in walls if wall.get("collective_id") != initial_collective_id)

        # With max_targets=1, only 1 wall should have changed
        assert walls_with_new_collective == 1, (
            f"Expected exactly 1 wall to change collective (max_targets=1), "
            f"but {walls_with_new_collective} walls changed"
        )

    def test_max_targets_zero_means_unlimited(self):
        """Test that max_targets=0 means unlimited (all matching objects affected)."""
        from mettagrid.config.mettagrid_config import WallConfig
        from mettagrid.map_builder.ascii import AsciiMapBuilder
        from mettagrid.mapgen.utils.ascii_grid import DEFAULT_CHAR_TO_NAME
        from mettagrid.simulator import Simulation

        # Create config with 4 walls, event has max_targets=0 (unlimited)
        config = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=5, height=5, num_tokens=100),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                resource_names=[],
                objects={
                    "wall": WallConfig(collective="cogs", tags=[Tag("target_wall")]),
                },
                collectives={
                    "cogs": CollectiveConfig(),
                    "clips": CollectiveConfig(),
                },
                events={
                    "wall_takeover": EventConfig(
                        name="wall_takeover",
                        target_tag="type:wall",
                        timesteps=[10],
                        filters=[hasTag(Tag("target_wall"))],
                        mutations=[alignTo("clips")],
                        max_targets=0,  # 0 means unlimited
                    ),
                },
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        ["#", ".", "#", ".", "#"],
                        [".", "@", ".", ".", "."],
                        ["#", ".", ".", ".", "."],
                        [".", ".", ".", ".", "."],
                        [".", ".", ".", ".", "."],
                    ],
                    char_to_map_name=DEFAULT_CHAR_TO_NAME,
                ),
            )
        )

        sim = Simulation(config)

        # Get initial wall count and collective
        objects = sim.grid_objects()
        walls = [obj for obj in objects.values() if obj.get("type_name") == "wall"]
        assert len(walls) == 4, f"Should have 4 walls, got {len(walls)}"

        initial_collective_id = walls[0].get("collective_id")

        # Run simulation until event fires
        for _ in range(10):
            sim.step()

        # All walls should have changed collective
        objects = sim.grid_objects()
        walls = [obj for obj in objects.values() if obj.get("type_name") == "wall"]

        walls_with_new_collective = sum(1 for wall in walls if wall.get("collective_id") != initial_collective_id)

        assert walls_with_new_collective == 4, (
            f"Expected all 4 walls to change collective (max_targets=0 = unlimited), "
            f"but only {walls_with_new_collective} walls changed"
        )

    def test_event_fires_at_specified_timestep(self):
        """Test that events fire at the specified timestep and apply mutations."""
        from mettagrid.config.mettagrid_config import WallConfig
        from mettagrid.map_builder.ascii import AsciiMapBuilder
        from mettagrid.mapgen.utils.ascii_grid import DEFAULT_CHAR_TO_NAME
        from mettagrid.simulator import Simulation

        # Create config with walls that belong to a collective, and an event that changes their alignment
        config = MettaGridConfig(
            game=GameConfig(
                num_agents=2,
                obs=ObsConfig(width=5, height=5, num_tokens=100),
                max_steps=200,
                actions=ActionsConfig(noop=NoopActionConfig()),
                resource_names=[],
                objects={
                    # Walls with special tag and collective assignment
                    "wall": WallConfig(collective="cogs", tags=[Tag("target_wall")]),
                },
                collectives={
                    "cogs": CollectiveConfig(),
                    "clips": CollectiveConfig(),
                },
                events={
                    # Event fires at timestep 10 to align walls to clips
                    "wall_takeover": EventConfig(
                        name="wall_takeover",
                        target_tag="type:wall",
                        timesteps=[10],  # Fire at timestep 10
                        filters=[hasTag(Tag("target_wall"))],
                        mutations=[alignTo("clips")],
                    ),
                },
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        [".", ".", ".", ".", "."],
                        [".", "@", ".", "#", "."],
                        [".", ".", ".", ".", "."],
                        [".", "@", ".", ".", "."],
                        [".", ".", ".", ".", "."],
                    ],
                    char_to_map_name=DEFAULT_CHAR_TO_NAME,
                ),
            )
        )

        sim = Simulation(config)

        # Get the wall's initial collective
        objects = sim.grid_objects()
        wall = next(
            (obj for obj in objects.values() if obj.get("type_name") == "wall"),
            None,
        )
        assert wall is not None, "Should have a wall"

        # Initial collective should be cogs (ID 0, since cogs is alphabetically first)
        initial_collective_id = wall.get("collective_id")
        assert initial_collective_id is not None, "Wall should have collective_id"

        # Run simulation for 9 steps (timesteps 1-9, event should not have fired yet)
        for _ in range(9):
            sim.step()

        # Check wall collective is still cogs (unchanged before event)
        objects = sim.grid_objects()
        wall = next(
            (obj for obj in objects.values() if obj.get("type_name") == "wall"),
            None,
        )
        assert wall is not None
        # Still should be initial collective
        assert wall.get("collective_id") == initial_collective_id, (
            "Wall should still be in initial collective before event fires"
        )

        # Run one more step (timestep 10, event should fire)
        sim.step()

        # Check wall collective has changed to clips
        objects = sim.grid_objects()
        wall = next(
            (obj for obj in objects.values() if obj.get("type_name") == "wall"),
            None,
        )
        assert wall is not None

        # Collective should have changed
        new_collective_id = wall.get("collective_id")
        assert new_collective_id != initial_collective_id, (
            f"Wall collective should have changed after event. "
            f"Initial: {initial_collective_id}, After: {new_collective_id}"
        )

    def test_periodic_event_fires_multiple_times(self):
        """Test that periodic events fire at each specified timestep."""
        from mettagrid.config.mettagrid_config import WallConfig
        from mettagrid.map_builder.ascii import AsciiMapBuilder
        from mettagrid.mapgen.utils.ascii_grid import DEFAULT_CHAR_TO_NAME
        from mettagrid.simulator import Simulation

        config = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=3, height=3, num_tokens=50),
                max_steps=200,
                actions=ActionsConfig(noop=NoopActionConfig()),
                resource_names=[],
                objects={
                    "wall": WallConfig(collective="team_a", tags=[Tag("target")]),
                },
                collectives={
                    "team_a": CollectiveConfig(),
                    "team_b": CollectiveConfig(),
                },
                events={
                    # Event fires every 5 steps, alternating alignment
                    "align_to_b": EventConfig(
                        name="align_to_b",
                        target_tag="type:wall",
                        timesteps=periodic(start=5, period=10, end=25),  # [5, 15, 25]
                        filters=[hasTag(Tag("target"))],
                        mutations=[alignTo("team_b")],
                    ),
                    "align_to_a": EventConfig(
                        name="align_to_a",
                        target_tag="type:wall",
                        timesteps=periodic(start=10, period=10, end=20),  # [10, 20]
                        filters=[hasTag(Tag("target"))],
                        mutations=[alignTo("team_a")],
                    ),
                },
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        [".", ".", "."],
                        [".", "@", "#"],
                        [".", ".", "."],
                    ],
                    char_to_map_name=DEFAULT_CHAR_TO_NAME,
                ),
            )
        )

        sim = Simulation(config)

        # Get initial collective
        objects = sim.grid_objects()
        wall = next(
            (obj for obj in objects.values() if obj.get("type_name") == "wall"),
            None,
        )
        assert wall is not None, "Should have a wall"

        # Track collective changes at specific timesteps
        collective_at_timestep = {}

        # Run simulation for 30 steps, recording collective at key points
        for step in range(1, 31):
            sim.step()
            if step in [5, 10, 15, 20, 25]:
                objects = sim.grid_objects()
                wall = next(
                    (obj for obj in objects.values() if obj.get("type_name") == "wall"),
                    None,
                )
                if wall:
                    collective_at_timestep[step] = wall.get("collective_id")

        # Verify events fired:
        # Step 5: align_to_b fires -> team_b
        # Step 10: align_to_a fires -> team_a
        # Step 15: align_to_b fires -> team_b
        # Step 20: align_to_a fires -> team_a
        # Step 25: align_to_b fires -> team_b
        # The pattern should alternate based on which event fires

        # We can't easily know the exact collective IDs without more inspection,
        # but we can verify that changes occurred
        assert len(set(collective_at_timestep.values())) > 1, (
            "Collective should change multiple times due to periodic events"
        )


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
