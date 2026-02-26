"""Tests for new GameValue types and string-parsing helpers."""

import pytest

from mettagrid.config.cpp_id_maps import CppIdMaps
from mettagrid.config.filter import hasTag
from mettagrid.config.game_value import (
    ConstValue,
    InventoryValue,
    NumObjectsValue,
    QueryCountValue,
    QueryInventoryValue,
    Scope,
    StatValue,
    SumGameValue,
    inv,
    log_weighted_sum,
    num,
    stat,
    tag,
    weighted_sum,
)
from mettagrid.config.mettagrid_c_value_config import resolve_game_value
from mettagrid.config.query import query
from mettagrid.config.tag import typeTag
from mettagrid.mettagrid_c import (
    ConstValueConfig as CppConstValueConfig,
)
from mettagrid.mettagrid_c import (
    InventoryValueConfig as CppInventoryValueConfig,
)
from mettagrid.mettagrid_c import (
    QueryCountValueConfig as CppQueryCountValueConfig,
)
from mettagrid.mettagrid_c import (
    QueryInventoryValueConfig as CppQueryInventoryValueConfig,
)
from mettagrid.mettagrid_c import (
    StatValueConfig as CppStatValueConfig,
)
from mettagrid.mettagrid_c import (
    SumValueConfig as CppSumValueConfig,
)


class TestScope:
    def test_values(self):
        assert Scope.AGENT.value == "agent"
        assert Scope.GAME.value == "game"


class TestInventoryValue:
    def test_default_scope(self):
        v = InventoryValue(item="gold")
        assert v.item == "gold"
        assert v.scope == Scope.AGENT


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

    def test_delta(self):
        v = stat("gold", delta=True)
        assert v.delta is True


class TestNumHelper:
    def test_basic(self):
        v = num("junction")
        assert isinstance(v, NumObjectsValue)
        assert v.object_type == "junction"

    def test_with_filter(self):
        v = num("junction", hasTag("team:cogs"))
        assert isinstance(v, QueryCountValue)


class TestTagHelper:
    def test_basic(self):
        v = tag("vibe:aligned")
        assert isinstance(v, QueryCountValue)
        assert v.query.source == "vibe:aligned"


class TestSumHelpers:
    def test_weighted_sum(self):
        value = weighted_sum([(2.0, StatValue(name="score")), (0.5, InventoryValue(item="gold"))])
        assert isinstance(value, SumGameValue)
        assert value.weights == [2.0, 0.5]
        assert value.log is False

    def test_log_weighted_sum(self):
        value = log_weighted_sum([(2.0, StatValue(name="score")), (0.5, InventoryValue(item="gold"))])
        assert isinstance(value, SumGameValue)
        assert value.weights == [2.0, 0.5]
        assert value.log is True


class TestResolveGameValueConversion:
    @staticmethod
    def _id_maps() -> CppIdMaps:
        return CppIdMaps(
            resource_name_to_id={"gold": 0, "wood": 1},
            tag_name_to_id={typeTag("junction"): 5, "vibe:aligned": 7},
            vibe_name_to_id={},
            limit_name_to_resource_ids={},
        )

    def test_inventory_value(self):
        cfg = resolve_game_value(InventoryValue(item="gold"), self._id_maps())
        assert isinstance(cfg, CppInventoryValueConfig)
        assert cfg.id == 0

    def test_stat_value(self):
        cfg = resolve_game_value(StatValue(name="score", scope=Scope.GAME, delta=True), self._id_maps())
        assert isinstance(cfg, CppStatValueConfig)
        assert cfg.delta is True
        assert cfg.stat_name == "score"

    def test_const_value(self):
        cfg = resolve_game_value(ConstValue(value=3.5), self._id_maps())
        assert isinstance(cfg, CppConstValueConfig)
        assert cfg.value == pytest.approx(3.5)

    def test_num_objects_value(self):
        cfg = resolve_game_value(NumObjectsValue(object_type="junction"), self._id_maps())
        assert isinstance(cfg, CppQueryCountValueConfig)

    def test_query_count_value(self):
        cfg = resolve_game_value(QueryCountValue(query=query("vibe:aligned")), self._id_maps())
        assert isinstance(cfg, CppQueryCountValueConfig)

    def test_query_inventory_value(self):
        cfg = resolve_game_value(QueryInventoryValue(query=query(typeTag("junction")), item="wood"), self._id_maps())
        assert isinstance(cfg, CppQueryInventoryValueConfig)
        assert cfg.id == 1

    def test_sum_value(self):
        value = SumGameValue(
            values=[InventoryValue(item="gold"), ConstValue(value=2.0)],
            weights=[2.0, 0.5],
            log=True,
        )
        cfg = resolve_game_value(value, self._id_maps())
        assert isinstance(cfg, CppSumValueConfig)
        assert len(cfg.values) == 2
        assert cfg.weights == [2.0, 0.5]
        assert cfg.log is True
