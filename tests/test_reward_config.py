"""Tests for reward and game value configuration models."""

import mettagrid.config.filter  # noqa: F401  # Ensure forward refs are rebuilt for game value models
from mettagrid.config.game_value import (
    ConstValue,
    GameValue,
    GameValueRatio,
    InventoryValue,
    MaxGameValue,
    MinGameValue,
    QueryCountValue,
    RatioGameValue,
    Scope,
    StatValue,
    SumGameValue,
    max_value,
    min_value,
    num,
    stat,
    val,
    weighted_sum,
)
from mettagrid.config.reward_config import AgentReward, reward
from mettagrid.config.tag import typeTag


def test_weighted_sum_and_log_weighted_sum():
    normal = weighted_sum([(2.0, StatValue(name="a")), (0.5, InventoryValue(item="heart"))])
    logged = weighted_sum([(2.0, StatValue(name="a")), (0.5, InventoryValue(item="heart"))], log=True)
    capped = weighted_sum([(2.0, StatValue(name="a"))], max=5.0)
    floored = weighted_sum([(2.0, StatValue(name="a"))], min=-1.0)
    assert isinstance(normal, SumGameValue)
    assert normal.weights == [2.0, 0.5]
    assert normal.log is False
    assert isinstance(logged, SumGameValue)
    assert logged.weights == [2.0, 0.5]
    assert logged.log is True
    assert isinstance(capped, MinGameValue)
    assert isinstance(floored, MaxGameValue)


def test_game_value_ratio_helper():
    ratio = GameValueRatio(StatValue(name="junction.held"), num(typeTag("junction")))
    assert isinstance(ratio, RatioGameValue)
    assert isinstance(ratio.numerator, GameValue)
    assert isinstance(ratio.denominator, GameValue)


def test_reward_helper_with_denominator_uses_ratio():
    ratio = GameValueRatio(
        weighted_sum([(0.1, StatValue(name="junction.held", scope=Scope.GAME))]),
        num(typeTag("junction")),
    )
    r = reward(min_value([ratio, val(5.0)]))
    assert isinstance(r, AgentReward)
    assert isinstance(r.reward, SumGameValue)
    assert len(r.reward.values) == 1
    inner = r.reward.values[0]
    assert isinstance(inner, MinGameValue)
    assert len(inner.values) == 2
    assert isinstance(inner.values[0], RatioGameValue)
    assert isinstance(inner.values[1], ConstValue)
    assert inner.values[1].value == 5.0


def test_reward_helper_negative_cap_uses_max_game_value():
    r = reward(max_value([weighted_sum([(-1.0, StatValue(name="aligner.lost"))]), val(-2.0)]))
    assert isinstance(r.reward, SumGameValue)
    assert len(r.reward.values) == 1
    inner = r.reward.values[0]
    assert isinstance(inner, MaxGameValue)
    assert len(inner.values) == 2
    assert isinstance(inner.values[1], ConstValue)
    assert inner.values[1].value == -2.0


def test_max_and_min_game_values():
    max_gv = max_value([val(1.0), val(3.0), val(2.0)])
    min_gv = min_value([val(1.0), val(3.0), val(2.0)])
    assert len(max_gv.values) == 3
    assert len(min_gv.values) == 3


def test_reward_basic_constructors():
    sr = reward(StatValue(name="score", delta=True), weight=0.2, per_tick=True)
    ir = reward(InventoryValue(item="heart"), weight=0.5)
    assert isinstance(sr.reward, SumGameValue)
    assert isinstance(ir.reward, SumGameValue)
    assert sr.per_tick is True


def test_reward_helper_supports_weight_and_clamp():
    r = reward(
        [StatValue(name="a"), StatValue(name="b")],
        weight=0.75,
        log=True,
        max=3.0,
    )
    assert isinstance(r.reward, MinGameValue)
    assert len(r.reward.values) == 2
    summed = r.reward.values[0]
    assert isinstance(summed, SumGameValue)
    assert summed.weights == [0.75, 0.75]
    assert summed.log is True
    assert isinstance(r.reward.values[1], ConstValue)
    assert r.reward.values[1].value == 3.0


def test_basic_value_helpers():
    s = stat("game.junction.held")
    o = num(typeTag("junction"))
    assert s.scope == Scope.GAME
    assert isinstance(o, QueryCountValue)
    assert o.query.source == typeTag("junction")


def test_reward_helper_preserves_ratio_denominator_order():
    d1 = num(typeTag("junction"))
    d2 = num(typeTag("hub"))
    r = reward(
        GameValueRatio(
            GameValueRatio(weighted_sum([(0.25, StatValue(name="junction.held", scope=Scope.GAME))]), d1),
            d2,
        )
    )

    assert isinstance(r.reward, SumGameValue)
    assert len(r.reward.values) == 1
    inner = r.reward.values[0]
    assert isinstance(inner, RatioGameValue)
    assert isinstance(inner.denominator, QueryCountValue)
    assert inner.denominator.query.source == typeTag("hub")
    assert isinstance(inner.numerator, RatioGameValue)
    assert isinstance(inner.numerator.denominator, QueryCountValue)
    assert inner.numerator.denominator.query.source == typeTag("junction")


def test_reward_helper_supports_log_aggregation_and_weight():
    d = num(typeTag("junction"))
    r = reward(GameValueRatio(weighted_sum([(0.75, StatValue(name="a")), (0.75, StatValue(name="b"))], log=True), d))

    assert isinstance(r.reward, SumGameValue)
    assert len(r.reward.values) == 1
    inner = r.reward.values[0]
    assert isinstance(inner, RatioGameValue)
    assert isinstance(inner.numerator, SumGameValue)
    assert inner.numerator.weights == [0.75, 0.75]
    assert inner.numerator.log is True
