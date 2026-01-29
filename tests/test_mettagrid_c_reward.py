"""Tests for reward conversion logic in mettagrid.config.mettagrid_c_reward.

This module tests convert_agent_rewards_to_stat_rewards() which converts
the Python AgentReward config format to the C++ stat_rewards format.
"""

import pytest

from mettagrid.config.game_value import (
    CollectiveInventory,
    Inventory,
    NumObjects,
    NumTaggedObjects,
    StatsSource,
    StatsValue,
)
from mettagrid.config.mettagrid_c_reward import convert_agent_rewards_to_stat_rewards
from mettagrid.config.reward_config import AgentReward


# Test fixtures
@pytest.fixture
def resource_name_to_id():
    """Sample resource name to ID mapping."""
    return {"heart": 0, "carbon": 1, "oxygen": 2, "gold": 3}


@pytest.fixture
def tag_name_to_id():
    """Sample tag name to ID mapping."""
    return {
        "type:junction": 10,
        "type:charger": 11,
        "type:assembler": 12,
        "vibe:aligned": 20,
        "vibe:scrambled": 21,
        "collective:cogs": 30,
        "collective:clips": 31,
    }


class TestStatsValueNumerator:
    """Test conversion of StatsValue numerators."""

    def test_basic_stats_value(self, resource_name_to_id, tag_name_to_id):
        """Test conversion of a basic StatsValue reward."""
        rewards = {
            "carbon_reward": AgentReward(
                nums=[StatsValue(name="carbon.gained")],
                weight=0.5,
            )
        }

        stat_rewards, stat_reward_max, stat_reward_denoms, stat_reward_stat_denoms = (
            convert_agent_rewards_to_stat_rewards(rewards, resource_name_to_id, tag_name_to_id)
        )

        assert "carbon.gained" in stat_rewards
        assert stat_rewards["carbon.gained"] == 0.5
        assert "carbon.gained" not in stat_reward_max
        assert "carbon.gained" not in stat_reward_denoms
        assert "carbon.gained" not in stat_reward_stat_denoms

    def test_stats_value_with_max(self, resource_name_to_id, tag_name_to_id):
        """Test StatsValue with max cap."""
        rewards = {
            "score": AgentReward(
                nums=[StatsValue(name="score")],
                weight=1.0,
                max=100.0,
            )
        }

        stat_rewards, stat_reward_max, _, _ = convert_agent_rewards_to_stat_rewards(
            rewards, resource_name_to_id, tag_name_to_id
        )

        assert stat_rewards["score"] == 1.0
        assert stat_reward_max["score"] == 100.0

    def test_stats_value_collective_source(self, resource_name_to_id, tag_name_to_id):
        """Test StatsValue with COLLECTIVE source."""
        rewards = {
            "held": AgentReward(
                nums=[StatsValue(name="aligned.junction.held", source=StatsSource.COLLECTIVE)],
                weight=0.1,
            )
        }

        stat_rewards, _, _, _ = convert_agent_rewards_to_stat_rewards(rewards, resource_name_to_id, tag_name_to_id)

        # The stat name is used as-is for collective stats
        assert "aligned.junction.held" in stat_rewards
        assert stat_rewards["aligned.junction.held"] == 0.1


class TestInventoryNumerator:
    """Test conversion of Inventory numerators."""

    def test_basic_inventory(self, resource_name_to_id, tag_name_to_id):
        """Test conversion of Inventory reward."""
        rewards = {
            "heart_reward": AgentReward(
                nums=[Inventory(item="heart")],
                weight=1.0,
            )
        }

        stat_rewards, _, _, _ = convert_agent_rewards_to_stat_rewards(rewards, resource_name_to_id, tag_name_to_id)

        # Inventory maps to {item}.amount
        assert "heart.amount" in stat_rewards
        assert stat_rewards["heart.amount"] == 1.0

    def test_inventory_with_max(self, resource_name_to_id, tag_name_to_id):
        """Test Inventory reward with max cap."""
        rewards = {
            "carbon": AgentReward(
                nums=[Inventory(item="carbon")],
                weight=0.5,
                max=50.0,
            )
        }

        stat_rewards, stat_reward_max, _, _ = convert_agent_rewards_to_stat_rewards(
            rewards, resource_name_to_id, tag_name_to_id
        )

        assert stat_rewards["carbon.amount"] == 0.5
        assert stat_reward_max["carbon.amount"] == 50.0

    def test_inventory_unknown_resource(self, resource_name_to_id, tag_name_to_id):
        """Test that unknown resource in Inventory raises error."""
        rewards = {
            "unknown": AgentReward(
                nums=[Inventory(item="unknown_item")],
            )
        }

        with pytest.raises(ValueError, match="Unknown resource 'unknown_item'"):
            convert_agent_rewards_to_stat_rewards(rewards, resource_name_to_id, tag_name_to_id)


class TestCollectiveInventoryNumerator:
    """Test conversion of CollectiveInventory numerators."""

    def test_basic_collective_inventory(self, resource_name_to_id, tag_name_to_id):
        """Test conversion of CollectiveInventory reward."""
        rewards = {
            "team_gold": AgentReward(
                nums=[CollectiveInventory(item="gold")],
                weight=0.25,
            )
        }

        stat_rewards, _, _, _ = convert_agent_rewards_to_stat_rewards(rewards, resource_name_to_id, tag_name_to_id)

        # CollectiveInventory maps to collective.{item}.amount
        assert "collective.gold.amount" in stat_rewards
        assert stat_rewards["collective.gold.amount"] == 0.25

    def test_collective_inventory_unknown_resource(self, resource_name_to_id, tag_name_to_id):
        """Test that unknown resource in CollectiveInventory raises error."""
        rewards = {
            "unknown": AgentReward(
                nums=[CollectiveInventory(item="unknown_item")],
            )
        }

        with pytest.raises(ValueError, match="Unknown resource 'unknown_item'"):
            convert_agent_rewards_to_stat_rewards(rewards, resource_name_to_id, tag_name_to_id)


class TestNumObjectsNumerator:
    """Test conversion of NumObjects numerators."""

    def test_basic_num_objects(self, resource_name_to_id, tag_name_to_id):
        """Test conversion of NumObjects reward."""
        rewards = {
            "junction_count": AgentReward(
                nums=[NumObjects(object_type="junction")],
                weight=0.1,
            )
        }

        stat_rewards, _, _, _ = convert_agent_rewards_to_stat_rewards(rewards, resource_name_to_id, tag_name_to_id)

        # NumObjects maps to tagcount:{tag_id}
        # type:junction has tag_id 10
        assert "tagcount:10" in stat_rewards
        assert stat_rewards["tagcount:10"] == 0.1

    def test_num_objects_missing_tag(self, resource_name_to_id, tag_name_to_id):
        """Test that NumObjects with missing type tag raises error."""
        rewards = {
            "unknown": AgentReward(
                nums=[NumObjects(object_type="unknown_type")],
            )
        }

        with pytest.raises(ValueError, match="type tag .* is not found"):
            convert_agent_rewards_to_stat_rewards(rewards, resource_name_to_id, tag_name_to_id)


class TestNumTaggedObjectsNumerator:
    """Test conversion of NumTaggedObjects numerators."""

    def test_basic_num_tagged_objects(self, resource_name_to_id, tag_name_to_id):
        """Test conversion of NumTaggedObjects reward."""
        rewards = {
            "aligned_count": AgentReward(
                nums=[NumTaggedObjects(tag="vibe:aligned")],
                weight=0.5,
            )
        }

        stat_rewards, _, _, _ = convert_agent_rewards_to_stat_rewards(rewards, resource_name_to_id, tag_name_to_id)

        # vibe:aligned has tag_id 20
        assert "tagcount:20" in stat_rewards
        assert stat_rewards["tagcount:20"] == 0.5

    def test_num_tagged_objects_missing_tag(self, resource_name_to_id, tag_name_to_id):
        """Test that NumTaggedObjects with missing tag raises error."""
        rewards = {
            "unknown": AgentReward(
                nums=[NumTaggedObjects(tag="unknown:tag")],
            )
        }

        with pytest.raises(ValueError, match="tag .* is not found"):
            convert_agent_rewards_to_stat_rewards(rewards, resource_name_to_id, tag_name_to_id)


class TestDenominators:
    """Test conversion of denominators."""

    def test_stats_value_denominator(self, resource_name_to_id, tag_name_to_id):
        """Test StatsValue as denominator."""
        rewards = {
            "normalized": AgentReward(
                nums=[StatsValue(name="score")],
                denoms=[StatsValue(name="total")],
                weight=1.0,
            )
        }

        _, _, stat_reward_denoms, stat_reward_stat_denoms = convert_agent_rewards_to_stat_rewards(
            rewards, resource_name_to_id, tag_name_to_id
        )

        assert "score" not in stat_reward_denoms
        assert stat_reward_stat_denoms["score"] == "total"

    def test_num_objects_denominator(self, resource_name_to_id, tag_name_to_id):
        """Test NumObjects as denominator."""
        rewards = {
            "per_junction": AgentReward(
                nums=[StatsValue(name="aligned.junction.held", source=StatsSource.COLLECTIVE)],
                denoms=[NumObjects(object_type="junction")],
                weight=0.1,
            )
        }

        _, _, stat_reward_denoms, stat_reward_stat_denoms = convert_agent_rewards_to_stat_rewards(
            rewards, resource_name_to_id, tag_name_to_id
        )

        # type:junction has tag_id 10
        assert stat_reward_denoms["aligned.junction.held"] == 10
        assert "aligned.junction.held" not in stat_reward_stat_denoms

    def test_num_tagged_objects_denominator(self, resource_name_to_id, tag_name_to_id):
        """Test NumTaggedObjects as denominator."""
        rewards = {
            "per_aligned": AgentReward(
                nums=[StatsValue(name="score")],
                denoms=[NumTaggedObjects(tag="vibe:aligned")],
                weight=1.0,
            )
        }

        _, _, stat_reward_denoms, _ = convert_agent_rewards_to_stat_rewards(
            rewards, resource_name_to_id, tag_name_to_id
        )

        # vibe:aligned has tag_id 20
        assert stat_reward_denoms["score"] == 20

    def test_inventory_denominator(self, resource_name_to_id, tag_name_to_id):
        """Test Inventory as denominator."""
        rewards = {
            "relative": AgentReward(
                nums=[StatsValue(name="score")],
                denoms=[Inventory(item="heart")],
                weight=1.0,
            )
        }

        _, _, stat_reward_denoms, stat_reward_stat_denoms = convert_agent_rewards_to_stat_rewards(
            rewards, resource_name_to_id, tag_name_to_id
        )

        assert "score" not in stat_reward_denoms
        assert stat_reward_stat_denoms["score"] == "heart.amount"

    def test_collective_inventory_denominator(self, resource_name_to_id, tag_name_to_id):
        """Test CollectiveInventory as denominator."""
        rewards = {
            "relative_to_team": AgentReward(
                nums=[StatsValue(name="my_score")],
                denoms=[CollectiveInventory(item="gold")],
                weight=1.0,
            )
        }

        _, _, _, stat_reward_stat_denoms = convert_agent_rewards_to_stat_rewards(
            rewards, resource_name_to_id, tag_name_to_id
        )

        assert stat_reward_stat_denoms["my_score"] == "collective.gold.amount"


class TestErrorHandling:
    """Test error handling in conversion."""

    def test_multiple_denominators_raises_error(self, resource_name_to_id, tag_name_to_id):
        """Test that multiple denominators raises ValueError."""
        rewards = {
            "invalid": AgentReward(
                nums=[StatsValue(name="score")],
                denoms=[
                    NumObjects(object_type="junction"),
                    NumObjects(object_type="charger"),
                ],
                weight=1.0,
            )
        }

        with pytest.raises(ValueError, match="only supports a single denominator"):
            convert_agent_rewards_to_stat_rewards(rewards, resource_name_to_id, tag_name_to_id)

    def test_duplicate_stat_reward_raises_error(self, resource_name_to_id, tag_name_to_id):
        """Test that duplicate stat rewards raise ValueError."""
        rewards = {
            "first": AgentReward(
                nums=[StatsValue(name="score")],
                weight=1.0,
            ),
            "second": AgentReward(
                nums=[StatsValue(name="score")],  # Same stat name
                weight=0.5,
            ),
        }

        with pytest.raises(ValueError, match="Duplicate stat reward"):
            convert_agent_rewards_to_stat_rewards(rewards, resource_name_to_id, tag_name_to_id)

    def test_duplicate_inventory_reward_raises_error(self, resource_name_to_id, tag_name_to_id):
        """Test that duplicate inventory rewards raise ValueError."""
        rewards = {
            "first": AgentReward(
                nums=[Inventory(item="heart")],
                weight=1.0,
            ),
            "second": AgentReward(
                nums=[Inventory(item="heart")],  # Same item
                weight=0.5,
            ),
        }

        with pytest.raises(ValueError, match="Duplicate inventory reward"):
            convert_agent_rewards_to_stat_rewards(rewards, resource_name_to_id, tag_name_to_id)

    def test_duplicate_num_objects_reward_raises_error(self, resource_name_to_id, tag_name_to_id):
        """Test that duplicate NumObjects rewards raise ValueError."""
        rewards = {
            "first": AgentReward(
                nums=[NumObjects(object_type="junction")],
                weight=1.0,
            ),
            "second": AgentReward(
                nums=[NumObjects(object_type="junction")],  # Same type
                weight=0.5,
            ),
        }

        with pytest.raises(ValueError, match="Duplicate NumObjects reward"):
            convert_agent_rewards_to_stat_rewards(rewards, resource_name_to_id, tag_name_to_id)

    def test_denominator_unknown_resource_raises_error(self, resource_name_to_id, tag_name_to_id):
        """Test that unknown resource in denominator raises error."""
        rewards = {
            "invalid": AgentReward(
                nums=[StatsValue(name="score")],
                denoms=[Inventory(item="unknown_item")],
                weight=1.0,
            )
        }

        with pytest.raises(ValueError, match="Unknown resource 'unknown_item'"):
            convert_agent_rewards_to_stat_rewards(rewards, resource_name_to_id, tag_name_to_id)

    def test_denominator_missing_tag_raises_error(self, resource_name_to_id, tag_name_to_id):
        """Test that missing tag in denominator raises error."""
        rewards = {
            "invalid": AgentReward(
                nums=[StatsValue(name="score")],
                denoms=[NumObjects(object_type="unknown_type")],
                weight=1.0,
            )
        }

        with pytest.raises(ValueError, match="type tag .* is not found"):
            convert_agent_rewards_to_stat_rewards(rewards, resource_name_to_id, tag_name_to_id)


class TestEmptyAndEdgeCases:
    """Test empty configs and edge cases."""

    def test_empty_rewards(self, resource_name_to_id, tag_name_to_id):
        """Test with empty rewards dict."""
        rewards = {}

        stat_rewards, stat_reward_max, stat_reward_denoms, stat_reward_stat_denoms = (
            convert_agent_rewards_to_stat_rewards(rewards, resource_name_to_id, tag_name_to_id)
        )

        assert stat_rewards == {}
        assert stat_reward_max == {}
        assert stat_reward_denoms == {}
        assert stat_reward_stat_denoms == {}

    def test_reward_with_empty_nums(self, resource_name_to_id, tag_name_to_id):
        """Test reward with no numerators (edge case)."""
        rewards = {"empty": AgentReward(nums=[], weight=1.0)}

        stat_rewards, _, _, _ = convert_agent_rewards_to_stat_rewards(rewards, resource_name_to_id, tag_name_to_id)

        # No numerators means no stat_rewards
        assert stat_rewards == {}

    def test_none_tag_name_to_id(self, resource_name_to_id):
        """Test with None tag_name_to_id (uses empty dict)."""
        rewards = {
            "simple": AgentReward(
                nums=[StatsValue(name="score")],
                weight=1.0,
            )
        }

        # Should not raise, uses empty dict for tags
        stat_rewards, _, _, _ = convert_agent_rewards_to_stat_rewards(rewards, resource_name_to_id, None)

        assert stat_rewards["score"] == 1.0


class TestMultipleRewards:
    """Test conversion of multiple rewards."""

    def test_multiple_different_rewards(self, resource_name_to_id, tag_name_to_id):
        """Test multiple rewards of different types."""
        rewards = {
            "stat_reward": AgentReward(
                nums=[StatsValue(name="score")],
                weight=1.0,
            ),
            "inventory_reward": AgentReward(
                nums=[Inventory(item="heart")],
                weight=0.5,
                max=10.0,
            ),
            "count_reward": AgentReward(
                nums=[NumObjects(object_type="junction")],
                weight=0.1,
                denoms=[NumObjects(object_type="charger")],
            ),
        }

        stat_rewards, stat_reward_max, stat_reward_denoms, _ = convert_agent_rewards_to_stat_rewards(
            rewards, resource_name_to_id, tag_name_to_id
        )

        # Check all rewards were converted
        assert stat_rewards["score"] == 1.0
        assert stat_rewards["heart.amount"] == 0.5
        assert "tagcount:10" in stat_rewards  # junction tag

        # Check max was set
        assert stat_reward_max["heart.amount"] == 10.0

        # Check denom was set for junction count
        assert stat_reward_denoms["tagcount:10"] == 11  # charger tag_id
