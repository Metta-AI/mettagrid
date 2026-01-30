"""Tests for GameValueFilter."""

from mettagrid.config.filter import GameValueFilter, HandlerTarget
from mettagrid.config.game_value import InventoryValue, Scope, StatValue


def test_game_value_filter_with_inventory():
    """Test GameValueFilter with an InventoryValue."""
    f = GameValueFilter(
        target=HandlerTarget.ACTOR,
        value=InventoryValue(item="gold", scope=Scope.AGENT),
        min=10,
    )
    assert f.filter_type == "game_value"
    assert f.min == 10
    assert isinstance(f.value, InventoryValue)
    assert f.value.item == "gold"


def test_game_value_filter_with_stat():
    """Test GameValueFilter with a StatValue."""
    f = GameValueFilter(
        target=HandlerTarget.TARGET,
        value=StatValue(name="carbon.gained", scope=Scope.GAME),
        min=5,
    )
    assert f.filter_type == "game_value"
    assert f.target == HandlerTarget.TARGET
    assert isinstance(f.value, StatValue)


def test_game_value_filter_default_min():
    """Test GameValueFilter defaults min to 0."""
    f = GameValueFilter(
        target=HandlerTarget.ACTOR,
        value=InventoryValue(item="gold"),
    )
    assert f.min == 0


def test_game_value_filter_serialization():
    """Test GameValueFilter round-trips through JSON."""
    f = GameValueFilter(
        target=HandlerTarget.ACTOR,
        value=InventoryValue(item="gold", scope=Scope.COLLECTIVE),
        min=3,
    )
    data = f.model_dump()
    assert data["filter_type"] == "game_value"
    assert data["min"] == 3
