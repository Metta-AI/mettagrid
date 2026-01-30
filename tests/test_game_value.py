"""Tests for new GameValue types and string-parsing helpers."""

import pytest

from mettagrid.config.game_value import (
    InventoryValue,
    NumObjectsValue,
    Scope,
    StatValue,
    TagCountValue,
    inv,
    num,
    stat,
    tag,
)


class TestScope:
    def test_values(self):
        assert Scope.AGENT.value == "agent"
        assert Scope.COLLECTIVE.value == "collective"
        assert Scope.GAME.value == "game"


class TestInventoryValue:
    def test_default_scope(self):
        v = InventoryValue(item="gold")
        assert v.item == "gold"
        assert v.scope == Scope.AGENT

    def test_collective_scope(self):
        v = InventoryValue(item="gold", scope=Scope.COLLECTIVE)
        assert v.scope == Scope.COLLECTIVE


class TestStatValue:
    def test_default(self):
        v = StatValue(name="carbon.gained")
        assert v.name == "carbon.gained"
        assert v.scope == Scope.AGENT
        assert v.delta is False

    def test_delta(self):
        v = StatValue(name="x", delta=True)
        assert v.delta is True


class TestInvHelper:
    def test_bare_item(self):
        v = inv("gold")
        assert isinstance(v, InventoryValue)
        assert v.item == "gold"
        assert v.scope == Scope.AGENT

    def test_agent_prefix(self):
        v = inv("agent.gold")
        assert v.item == "gold"
        assert v.scope == Scope.AGENT

    def test_collective_prefix(self):
        v = inv("collective.gold")
        assert v.item == "gold"
        assert v.scope == Scope.COLLECTIVE

    def test_game_scope_disallowed(self):
        with pytest.raises(ValueError):
            inv("game.gold")


class TestStatHelper:
    def test_bare_name(self):
        v = stat("carbon.gained")
        assert isinstance(v, StatValue)
        assert v.name == "carbon.gained"
        assert v.scope == Scope.AGENT

    def test_agent_prefix_dotted_name(self):
        v = stat("agent.carbon.gained")
        assert v.name == "carbon.gained"
        assert v.scope == Scope.AGENT

    def test_game_prefix(self):
        v = stat("game.junctions")
        assert v.name == "junctions"
        assert v.scope == Scope.GAME

    def test_collective_prefix(self):
        v = stat("collective.foo")
        assert v.name == "foo"
        assert v.scope == Scope.COLLECTIVE

    def test_delta(self):
        v = stat("gold", delta=True)
        assert v.delta is True


class TestNumHelper:
    def test_basic(self):
        v = num("junction")
        assert isinstance(v, NumObjectsValue)
        assert v.object_type == "junction"


class TestTagHelper:
    def test_basic(self):
        v = tag("vibe:aligned")
        assert isinstance(v, TagCountValue)
        assert v.tag == "vibe:aligned"
