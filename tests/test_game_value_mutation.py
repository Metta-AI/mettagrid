"""Tests for SetGameValueMutation."""

from mettagrid.config.game_value import InventoryValue, Scope, StatValue
from mettagrid.config.mutation import EntityTarget, SetGameValueMutation


def test_set_game_value_mutation_inventory():
    """Test SetGameValueMutation with InventoryValue."""
    m = SetGameValueMutation(
        value=InventoryValue(item="gold", scope=Scope.AGENT),
        delta=5,
    )
    assert m.mutation_type == "set_game_value"
    assert m.delta == 5
    assert m.target == EntityTarget.ACTOR
    assert isinstance(m.value, InventoryValue)


def test_set_game_value_mutation_stat():
    """Test SetGameValueMutation with StatValue."""
    m = SetGameValueMutation(
        value=StatValue(name="carbon.gained", scope=Scope.GAME),
        delta=-3,
        target=EntityTarget.TARGET,
    )
    assert m.mutation_type == "set_game_value"
    assert m.delta == -3
    assert m.target == EntityTarget.TARGET
    assert isinstance(m.value, StatValue)


def test_set_game_value_mutation_serialization():
    """Test SetGameValueMutation round-trips through JSON."""
    m = SetGameValueMutation(
        value=InventoryValue(item="silver", scope=Scope.COLLECTIVE),
        delta=10,
        target=EntityTarget.ACTOR_COLLECTIVE,
    )
    data = m.model_dump()
    assert data["mutation_type"] == "set_game_value"
    assert data["delta"] == 10
