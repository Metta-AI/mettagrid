"""Tests for reward configuration in mettagrid.config.reward_config.

Also includes tests for GameValue types from mettagrid.config.game_value.
"""

import pytest

from mettagrid.config.game_value import (
    AnyGameValue,
    CollectiveInventory,
    GameValue,
    Inventory,
    NumObjects,
    NumTaggedObjects,
    StatsSource,
    StatsValue,
)
from mettagrid.config.reward_config import (
    AgentReward,
    collectiveInventoryReward,
    inventoryReward,
    numObjects,
    numObjectsReward,
    numTaggedReward,
    reward,
    stat,
    statReward,
)

# =============================================================================
# GameValue Type Tests
# =============================================================================


class TestStatsSource:
    """Test StatsSource enum."""

    def test_enum_values(self):
        """Test that StatsSource has expected values."""
        assert StatsSource.OWN.value == "own"
        assert StatsSource.GLOBAL.value == "global"
        assert StatsSource.COLLECTIVE.value == "collective"

    def test_all_sources(self):
        """Test that all expected sources exist."""
        sources = list(StatsSource)
        assert len(sources) == 3
        assert StatsSource.OWN in sources
        assert StatsSource.GLOBAL in sources
        assert StatsSource.COLLECTIVE in sources


class TestGameValueInheritance:
    """Test GameValue inheritance and type checking."""

    def test_all_types_inherit_from_game_value(self):
        """Test that all GameValue types inherit from GameValue base."""
        assert issubclass(StatsValue, GameValue)
        assert issubclass(Inventory, GameValue)
        assert issubclass(CollectiveInventory, GameValue)
        assert issubclass(NumObjects, GameValue)
        assert issubclass(NumTaggedObjects, GameValue)

    def test_instances_are_game_values(self):
        """Test that instances are GameValue instances."""
        values = [
            StatsValue(name="test"),
            Inventory(item="heart"),
            CollectiveInventory(item="gold"),
            NumObjects(object_type="junction"),
            NumTaggedObjects(tag="vibe:aligned"),
        ]
        for v in values:
            assert isinstance(v, GameValue)


class TestAnyGameValueUnion:
    """Test the AnyGameValue union type."""

    def test_union_accepts_all_types(self):
        """Test that AnyGameValue union accepts all GameValue types."""
        values: list[AnyGameValue] = [
            StatsValue(name="test"),
            Inventory(item="heart"),
            CollectiveInventory(item="gold"),
            NumObjects(object_type="junction"),
            NumTaggedObjects(tag="vibe:aligned"),
        ]
        assert len(values) == 5


# =============================================================================
# AgentReward Tests
# =============================================================================


class TestAgentReward:
    """Test AgentReward configuration class."""

    def test_default_values(self):
        """Test AgentReward default values."""
        ar = AgentReward()
        assert ar.nums == []
        assert ar.denoms == []
        assert ar.weight == 1.0
        assert ar.max is None

    def test_with_single_numerator(self):
        """Test AgentReward with a single numerator."""
        ar = AgentReward(nums=[StatsValue(name="carbon.gained")])
        assert len(ar.nums) == 1
        assert isinstance(ar.nums[0], StatsValue)
        assert ar.nums[0].name == "carbon.gained"

    def test_with_multiple_numerators(self):
        """Test AgentReward with multiple numerators."""
        ar = AgentReward(
            nums=[
                StatsValue(name="a.b"),
                Inventory(item="heart"),
            ]
        )
        assert len(ar.nums) == 2

    def test_with_denominator(self):
        """Test AgentReward with denominator."""
        ar = AgentReward(
            nums=[StatsValue(name="aligned.junction.held")],
            denoms=[NumObjects(object_type="junction")],
        )
        assert len(ar.denoms) == 1
        assert isinstance(ar.denoms[0], NumObjects)

    def test_with_weight_and_max(self):
        """Test AgentReward with custom weight and max cap."""
        ar = AgentReward(nums=[Inventory(item="heart")], weight=0.5, max=10.0)
        assert ar.weight == 0.5
        assert ar.max == 10.0

    def test_full_config(self):
        """Test AgentReward with all fields."""
        ar = AgentReward(
            nums=[StatsValue(name="aligned.junction.held", source=StatsSource.COLLECTIVE)],
            denoms=[NumObjects(object_type="junction")],
            weight=0.1,
            max=5.0,
        )
        assert len(ar.nums) == 1
        assert len(ar.denoms) == 1
        assert ar.weight == 0.1
        assert ar.max == 5.0

    def test_serialization(self):
        """Test AgentReward serialization."""
        ar = AgentReward(
            nums=[Inventory(item="heart")],
            weight=0.5,
            max=10.0,
        )
        data = ar.model_dump()
        assert data["weight"] == 0.5
        assert data["max"] == 10.0
        assert len(data["nums"]) == 1
        assert data["nums"][0]["item"] == "heart"


# =============================================================================
# Helper Function Tests (Parameterized)
# =============================================================================


class TestStatHelper:
    """Test the stat() helper function."""

    def test_basic_stat(self):
        """Test basic stat creation."""
        s = stat("carbon.gained")
        assert isinstance(s, StatsValue)
        assert s.name == "carbon.gained"
        assert s.source == StatsSource.OWN
        assert s.delta is False

    def test_stat_with_source(self):
        """Test stat with custom source."""
        s = stat("aligned.junction.held", source=StatsSource.COLLECTIVE)
        assert s.source == StatsSource.COLLECTIVE

    def test_stat_with_delta(self):
        """Test stat with delta flag."""
        s = stat("score", delta=True)
        assert s.delta is True

    def test_stats_value_serialization_round_trip(self):
        """Test StatsValue serialization/deserialization."""
        original = StatsValue(name="carbon.gained", source=StatsSource.COLLECTIVE, delta=True)
        data = original.model_dump()
        restored = StatsValue.model_validate(data)

        assert restored.name == original.name
        assert restored.source == original.source
        assert restored.delta == original.delta


class TestRewardHelper:
    """Test the reward() helper function."""

    def test_basic_reward(self):
        """Test basic reward creation."""
        r = reward(StatsValue(name="test"))
        assert isinstance(r, AgentReward)
        assert len(r.nums) == 1
        assert r.weight == 1.0
        assert r.max is None

    def test_reward_with_weight_max_denoms(self):
        """Test reward with all options."""
        r = reward(
            StatsValue(name="aligned.junction.held"),
            weight=0.5,
            max=10.0,
            denoms=[NumObjects(object_type="junction")],
        )
        assert r.weight == 0.5
        assert r.max == 10.0
        assert len(r.denoms) == 1


# Parameterized tests for reward helper functions
REWARD_HELPER_TEST_CASES = [
    # (helper_fn, args, expected_num_type, expected_field, expected_field_value)
    ("inventoryReward", ("heart",), Inventory, "item", "heart"),
    ("collectiveInventoryReward", ("gold",), CollectiveInventory, "item", "gold"),
    ("numObjectsReward", ("junction",), NumObjects, "object_type", "junction"),
    ("numTaggedReward", ("vibe:aligned",), NumTaggedObjects, "tag", "vibe:aligned"),
]


class TestRewardHelpers:
    """Parameterized tests for reward helper functions."""

    @pytest.mark.parametrize("helper_name,args,expected_type,field,value", REWARD_HELPER_TEST_CASES)
    def test_basic_creation(self, helper_name, args, expected_type, field, value):
        """Test that helper creates correct reward with expected numerator type."""
        helper_fn = {
            "inventoryReward": inventoryReward,
            "collectiveInventoryReward": collectiveInventoryReward,
            "numObjectsReward": numObjectsReward,
            "numTaggedReward": numTaggedReward,
        }[helper_name]

        r = helper_fn(*args)
        assert isinstance(r, AgentReward)
        assert len(r.nums) == 1
        assert isinstance(r.nums[0], expected_type)
        assert getattr(r.nums[0], field) == value
        assert r.weight == 1.0
        assert r.max is None

    @pytest.mark.parametrize("helper_name,args,expected_type,field,value", REWARD_HELPER_TEST_CASES)
    def test_with_weight(self, helper_name, args, expected_type, field, value):
        """Test that helper respects weight parameter."""
        helper_fn = {
            "inventoryReward": inventoryReward,
            "collectiveInventoryReward": collectiveInventoryReward,
            "numObjectsReward": numObjectsReward,
            "numTaggedReward": numTaggedReward,
        }[helper_name]

        r = helper_fn(*args, weight=0.5)
        assert r.weight == 0.5

    @pytest.mark.parametrize("helper_name,args,expected_type,field,value", REWARD_HELPER_TEST_CASES)
    def test_with_max(self, helper_name, args, expected_type, field, value):
        """Test that helper respects max parameter."""
        helper_fn = {
            "inventoryReward": inventoryReward,
            "collectiveInventoryReward": collectiveInventoryReward,
            "numObjectsReward": numObjectsReward,
            "numTaggedReward": numTaggedReward,
        }[helper_name]

        r = helper_fn(*args, max=100.0)
        assert r.max == 100.0


class TestNumObjectsHelper:
    """Test the numObjects() helper function."""

    def test_basic_num_objects(self):
        """Test basic numObjects creation."""
        no = numObjects("junction")
        assert isinstance(no, NumObjects)
        assert no.object_type == "junction"

    def test_serialization_round_trip(self):
        """Test NumObjects serialization/deserialization."""
        original = NumObjects(object_type="charger")
        data = original.model_dump()
        restored = NumObjects.model_validate(data)
        assert restored.object_type == original.object_type


class TestStatReward:
    """Test the statReward() helper function."""

    def test_basic_stat_reward(self):
        """Test basic stat reward."""
        r = statReward("carbon.gained")
        assert isinstance(r, AgentReward)
        assert len(r.nums) == 1
        assert isinstance(r.nums[0], StatsValue)
        assert r.nums[0].name == "carbon.gained"
        assert r.nums[0].source == StatsSource.OWN

    def test_stat_reward_with_source(self):
        """Test stat reward with custom source."""
        r = statReward("aligned.junction.held", source=StatsSource.COLLECTIVE)
        assert r.nums[0].source == StatsSource.COLLECTIVE

    def test_stat_reward_with_delta(self):
        """Test stat reward with delta flag."""
        r = statReward("score", delta=True)
        assert r.nums[0].delta is True

    def test_stat_reward_full_config(self):
        """Test stat reward with all options."""
        r = statReward(
            "aligned.junction.held",
            source=StatsSource.COLLECTIVE,
            delta=False,
            weight=0.1,
            max=5.0,
            denoms=[NumObjects(object_type="junction")],
        )
        assert r.nums[0].name == "aligned.junction.held"
        assert r.nums[0].source == StatsSource.COLLECTIVE
        assert r.nums[0].delta is False
        assert r.weight == 0.1
        assert r.max == 5.0
        assert len(r.denoms) == 1


# =============================================================================
# Serialization Round-Trip Tests
# =============================================================================


class TestRewardConfigSerialization:
    """Test serialization/deserialization of reward configs."""

    def test_round_trip_simple_reward(self):
        """Test serialization round-trip for simple reward."""
        original = inventoryReward("heart", weight=0.5, max=10.0)
        data = original.model_dump()
        restored = AgentReward.model_validate(data)

        assert restored.weight == original.weight
        assert restored.max == original.max
        assert len(restored.nums) == len(original.nums)

    def test_round_trip_complex_reward(self):
        """Test serialization round-trip for complex reward with denoms."""
        original = statReward(
            "aligned.junction.held",
            source=StatsSource.COLLECTIVE,
            weight=0.1,
            max=5.0,
            denoms=[NumObjects(object_type="junction")],
        )
        data = original.model_dump()
        restored = AgentReward.model_validate(data)

        assert restored.weight == original.weight
        assert restored.max == original.max
        assert len(restored.nums) == 1
        assert len(restored.denoms) == 1

    @pytest.mark.parametrize(
        "game_value",
        [
            Inventory(item="heart"),
            CollectiveInventory(item="gold"),
            NumObjects(object_type="junction"),
            NumTaggedObjects(tag="vibe:aligned"),
        ],
    )
    def test_game_value_round_trip(self, game_value):
        """Test serialization round-trip for individual GameValue types."""
        data = game_value.model_dump()
        restored = type(game_value).model_validate(data)

        # Compare all fields
        assert data == restored.model_dump()
