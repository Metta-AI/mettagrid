import math

from mettagrid.config.game_value import (
    GameValueRatio,
    InventoryValue,
    max_value,
    min_value,
    val,
    weighted_sum,
)
from mettagrid.config.game_value import stat as game_stat
from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    AgentConfig,
    GameConfig,
    InventoryConfig,
    MettaGridConfig,
    NoopActionConfig,
    WallConfig,
)
from mettagrid.config.reward_config import reward
from mettagrid.simulator import Action, Simulation
from mettagrid.test_support.map_builders import ObjectNameMapBuilder


class TestStatReward:
    """Test statReward helper function integration."""

    def test_stat_reward_tracks_stat_changes(self):
        """Test that statReward correctly tracks stat changes."""
        game_map = [
            ["wall", "wall", "wall"],
            ["wall", "agent.red", "wall"],
            ["wall", "wall", "wall"],
        ]

        game_config = GameConfig(
            max_steps=100,
            num_agents=1,
            resource_names=["gold"],
            actions=ActionsConfig(
                noop=NoopActionConfig(enabled=True),
            ),
            objects={
                "wall": WallConfig(),
            },
            agent=AgentConfig(
                inventory=InventoryConfig(initial={"gold": 5}),
                rewards={
                    "gold": reward(weighted_sum([(0.1, game_stat("gold.amount"))])),
                },
            ),
        )

        cfg = MettaGridConfig(game=game_config)
        cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=game_map)
        sim = Simulation(cfg, seed=42)
        agent = sim.agent(0)

        # Take a step
        agent.set_action(Action(name="noop"))
        sim.step()

        # Should have reward from initial gold (5 * 0.1 = 0.5)
        assert agent.episode_reward > 0, "Should have positive reward from gold stat"


class TestMultipleRewardTypes:
    """Test multiple reward types in a single agent config."""

    def test_multiple_rewards_accumulate(self):
        """Test that multiple reward types all contribute to total reward."""
        game_map = [
            ["wall", "wall", "wall"],
            ["wall", "agent.red", "wall"],
            ["wall", "wall", "wall"],
        ]

        game_config = GameConfig(
            max_steps=100,
            num_agents=1,
            resource_names=["gold", "silver"],
            actions=ActionsConfig(
                noop=NoopActionConfig(enabled=True),
            ),
            objects={
                "wall": WallConfig(),
            },
            agent=AgentConfig(
                inventory=InventoryConfig(initial={"gold": 10, "silver": 5}),
                rewards={
                    # Multiple reward sources
                    "gold": reward(weighted_sum([(0.1, InventoryValue(item="gold"))])),
                    "silver": reward(weighted_sum([(0.2, InventoryValue(item="silver"))])),
                },
            ),
        )

        cfg = MettaGridConfig(game=game_config)
        cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=game_map)
        sim = Simulation(cfg, seed=42)
        agent = sim.agent(0)

        # Take a step
        agent.set_action(Action(name="noop"))
        sim.step()

        # Should have rewards from both gold and silver
        # gold: 10 * 0.1 = 1.0
        # silver: 5 * 0.2 = 1.0
        # total: 2.0
        expected = 10 * 0.1 + 5 * 0.2
        assert abs(agent.episode_reward - expected) < 0.01, (
            f"Expected reward around {expected}, got {agent.episode_reward}"
        )


class TestPerTickReward:
    """Test per_tick=True vs per_tick=False (default delta mode)."""

    def _make_sim(self, per_tick: bool):
        game_map = [
            ["wall", "wall", "wall"],
            ["wall", "agent.red", "wall"],
            ["wall", "wall", "wall"],
        ]
        game_config = GameConfig(
            max_steps=100,
            num_agents=1,
            resource_names=["gold"],
            actions=ActionsConfig(noop=NoopActionConfig(enabled=True)),
            objects={"wall": WallConfig()},
            agent=AgentConfig(
                inventory=InventoryConfig(initial={"gold": 10}),
                rewards={
                    "gold": reward(weighted_sum([(0.1, InventoryValue(item="gold"))]), per_tick=per_tick),
                },
            ),
        )
        cfg = MettaGridConfig(game=game_config)
        cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=game_map)
        return Simulation(cfg, seed=42)

    def test_default_delta_mode_rewards_only_on_change(self):
        """per_tick=False: constant inventory produces reward only on first tick (delta from 0)."""
        sim = self._make_sim(per_tick=False)
        agent = sim.agent(0)

        agent.set_action(Action(name="noop"))
        sim.step()
        reward_after_1 = agent.episode_reward

        for _ in range(9):
            agent.set_action(Action(name="noop"))
            sim.step()
        reward_after_10 = agent.episode_reward

        assert abs(reward_after_1 - 1.0) < 0.01, f"First tick delta should be ~1.0, got {reward_after_1}"
        assert abs(reward_after_10 - reward_after_1) < 0.01, (
            f"No further reward when inventory is constant: after_1={reward_after_1}, after_10={reward_after_10}"
        )

    def test_per_tick_mode_accumulates_every_tick(self):
        """per_tick=True: constant inventory produces reward every single tick."""
        sim = self._make_sim(per_tick=True)
        agent = sim.agent(0)

        agent.set_action(Action(name="noop"))
        sim.step()
        reward_after_1 = agent.episode_reward

        for _ in range(9):
            agent.set_action(Action(name="noop"))
            sim.step()
        reward_after_10 = agent.episode_reward

        assert abs(reward_after_1 - 1.0) < 0.01, f"First tick should be ~1.0, got {reward_after_1}"
        assert abs(reward_after_10 - 10.0) < 0.01, f"After 10 ticks should be ~10.0, got {reward_after_10}"

    def test_per_tick_current_stat_reward_nonzero(self):
        """per_tick=True: current_stat_reward in grid_objects() reflects the per-tick value, not 0."""
        sim = self._make_sim(per_tick=True)
        agent = sim.agent(0)

        for _ in range(3):
            agent.set_action(Action(name="noop"))
            sim.step()

        agent_objs = [o for o in sim.grid_objects().values() if "agent_id" in o]
        assert len(agent_objs) == 1
        assert agent_objs[0]["current_stat_reward"] != 0.0, (
            f"current_stat_reward should reflect per-tick value, got {agent_objs[0]['current_stat_reward']}"
        )

    def test_per_tick_vs_default_diverge_on_constant_value(self):
        """Directly compare both modes: they agree on tick 1 but diverge after."""
        sim_delta = self._make_sim(per_tick=False)
        sim_accum = self._make_sim(per_tick=True)
        agent_delta = sim_delta.agent(0)
        agent_accum = sim_accum.agent(0)

        num_steps = 5
        for _ in range(num_steps):
            agent_delta.set_action(Action(name="noop"))
            sim_delta.step()
            agent_accum.set_action(Action(name="noop"))
            sim_accum.step()

        assert abs(agent_delta.episode_reward - 1.0) < 0.01, (
            f"Delta mode should stay at ~1.0, got {agent_delta.episode_reward}"
        )
        assert abs(agent_accum.episode_reward - 5.0) < 0.01, (
            f"Accumulate mode should reach ~5.0, got {agent_accum.episode_reward}"
        )


class TestSumLogsAggregation:
    """Test that SUM_LOGS aggregation computes sum(log(val + 1)) across numerators."""

    def test_sum_logs_computes_log_sum_of_inventory_amounts(self):
        """SUM_LOGS with inventory values should give sum(log(amount + 1))."""
        game_map = [
            ["wall", "wall", "wall"],
            ["wall", "agent.red", "wall"],
            ["wall", "wall", "wall"],
        ]

        game_config = GameConfig(
            max_steps=100,
            num_agents=1,
            resource_names=["gold", "silver"],
            actions=ActionsConfig(noop=NoopActionConfig(enabled=True)),
            objects={"wall": WallConfig()},
            agent=AgentConfig(
                inventory=InventoryConfig(initial={"gold": 10, "silver": 5}),
                rewards={
                    "diversity": reward(
                        weighted_sum([(1.0, game_stat("gold.amount")), (1.0, game_stat("silver.amount"))], log=True),
                    ),
                },
            ),
        )

        cfg = MettaGridConfig(game=game_config)
        cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=game_map)
        sim = Simulation(cfg, seed=42)
        agent = sim.agent(0)

        agent.set_action(Action(name="noop"))
        sim.step()

        # Expected: log(10 + 1) + log(5 + 1) = log(11) + log(6)
        expected = math.log(11) + math.log(6)
        assert abs(agent.episode_reward - expected) < 0.01, (
            f"Expected reward ~{expected:.4f}, got {agent.episode_reward:.4f}"
        )

    def test_sum_logs_zero_values_contribute_zero(self):
        """log(0 + 1) = 0, so zero-valued stats don't contribute."""
        game_map = [
            ["wall", "wall", "wall"],
            ["wall", "agent.red", "wall"],
            ["wall", "wall", "wall"],
        ]

        game_config = GameConfig(
            max_steps=100,
            num_agents=1,
            resource_names=["gold", "silver"],
            actions=ActionsConfig(noop=NoopActionConfig(enabled=True)),
            objects={"wall": WallConfig()},
            agent=AgentConfig(
                inventory=InventoryConfig(initial={"gold": 0, "silver": 0}),
                rewards={
                    "diversity": reward(
                        weighted_sum([(1.0, game_stat("gold.amount")), (1.0, game_stat("silver.amount"))], log=True),
                    ),
                },
            ),
        )

        cfg = MettaGridConfig(game=game_config)
        cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=game_map)
        sim = Simulation(cfg, seed=42)
        agent = sim.agent(0)

        agent.set_action(Action(name="noop"))
        sim.step()

        # log(0+1) + log(0+1) = 0 + 0 = 0
        assert agent.episode_reward == 0.0, f"Expected 0 reward for zero stats, got {agent.episode_reward}"


class TestMultiNumeratorSum:
    """Test that multi-numerator SUM aggregation sums values."""

    def test_multi_numerator_sum(self):
        """Multiple numerators with SUM should add their values."""
        game_map = [
            ["wall", "wall", "wall"],
            ["wall", "agent.red", "wall"],
            ["wall", "wall", "wall"],
        ]

        game_config = GameConfig(
            max_steps=100,
            num_agents=1,
            resource_names=["gold", "silver"],
            actions=ActionsConfig(noop=NoopActionConfig(enabled=True)),
            objects={"wall": WallConfig()},
            agent=AgentConfig(
                inventory=InventoryConfig(initial={"gold": 10, "silver": 5}),
                rewards={
                    "total": reward(
                        weighted_sum([(0.5, game_stat("gold.amount")), (0.5, game_stat("silver.amount"))]),
                    ),
                },
            ),
        )

        cfg = MettaGridConfig(game=game_config)
        cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=game_map)
        sim = Simulation(cfg, seed=42)
        agent = sim.agent(0)

        agent.set_action(Action(name="noop"))
        sim.step()

        # Expected: (10 + 5) * 0.5 = 7.5
        expected = (10 + 5) * 0.5
        assert abs(agent.episode_reward - expected) < 0.01, f"Expected reward ~{expected}, got {agent.episode_reward}"


class TestRatioReward:
    """Reward ratios should handle denominator edge-cases safely."""

    def test_ratio_with_zero_denominator_returns_numerator(self):
        game_map = [
            ["wall", "wall", "wall"],
            ["wall", "agent.red", "wall"],
            ["wall", "wall", "wall"],
        ]

        game_config = GameConfig(
            max_steps=100,
            num_agents=1,
            resource_names=["gold"],
            actions=ActionsConfig(noop=NoopActionConfig(enabled=True)),
            objects={"wall": WallConfig()},
            agent=AgentConfig(
                rewards={
                    "ratio": reward(
                        weighted_sum(
                            [
                                (
                                    1.0,
                                    GameValueRatio(
                                        game_stat("gold.amount"),
                                        game_stat("silver.amount"),
                                    ),
                                )
                            ]
                        ),
                    ),
                },
                inventory=InventoryConfig(initial={"gold": 10}),
            ),
        )

        cfg = MettaGridConfig(game=game_config)
        cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=game_map)
        sim = Simulation(cfg, seed=42)
        agent = sim.agent(0)
        agent.set_action(Action(name="noop"))
        sim.step()
        assert abs(agent.episode_reward - 10.0) < 0.01


class TestMinMaxGameValueRewards:
    """Runtime behavior tests for min/max combinator game values."""

    def _make_single_agent_sim(self, reward_value):
        game_map = [
            ["wall", "wall", "wall"],
            ["wall", "agent.red", "wall"],
            ["wall", "wall", "wall"],
        ]
        game_config = GameConfig(
            max_steps=100,
            num_agents=1,
            resource_names=["gold"],
            actions=ActionsConfig(noop=NoopActionConfig(enabled=True)),
            objects={"wall": WallConfig()},
            agent=AgentConfig(
                inventory=InventoryConfig(initial={"gold": 10}),
                rewards={"combo": reward(weighted_sum([(1.0, reward_value)]))},
            ),
        )
        cfg = MettaGridConfig(game=game_config)
        cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=game_map)
        return Simulation(cfg, seed=42)

    def test_min_value_caps_reward(self):
        sim = self._make_single_agent_sim(min_value([game_stat("gold.amount"), val(3.0)]))
        agent = sim.agent(0)
        agent.set_action(Action(name="noop"))
        sim.step()
        assert abs(agent.episode_reward - 3.0) < 0.01

    def test_max_value_floors_reward(self):
        sim = self._make_single_agent_sim(max_value([game_stat("gold.amount"), val(12.0)]))
        agent = sim.agent(0)
        agent.set_action(Action(name="noop"))
        sim.step()
        assert abs(agent.episode_reward - 12.0) < 0.01
