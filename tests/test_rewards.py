import pytest

from mettagrid.config.game_value import stat as game_stat
from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    AgentConfig,
    CollectiveConfig,
    GameConfig,
    GridObjectConfig,
    InventoryConfig,
    MettaGridConfig,
    NoopActionConfig,
    WallConfig,
)
from mettagrid.config.reward_config import inventoryReward, reward, statReward
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
            collectives={
                "team": CollectiveConfig(inventory=InventoryConfig()),
            },
            objects={
                "wall": WallConfig(),
            },
            agent=AgentConfig(
                collective="team",
                inventory=InventoryConfig(initial={"gold": 5}),
                # Reward based on gold amount stat
                rewards={
                    "gold": statReward("gold.amount", weight=0.1),
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
            ["wall", "wall", "wall", "wall", "wall"],
            ["wall", "agent.red", "empty", "junction", "wall"],
            ["wall", "wall", "wall", "wall", "wall"],
        ]

        game_config = GameConfig(
            max_steps=100,
            num_agents=1,
            resource_names=["gold", "silver"],
            actions=ActionsConfig(
                noop=NoopActionConfig(enabled=True),
            ),
            collectives={
                "team": CollectiveConfig(inventory=InventoryConfig()),
            },
            objects={
                "wall": WallConfig(),
                "junction": GridObjectConfig(name="junction", collective="team"),
            },
            agent=AgentConfig(
                collective="team",
                inventory=InventoryConfig(initial={"gold": 10, "silver": 5}),
                rewards={
                    # Multiple reward sources
                    "gold": inventoryReward("gold", weight=0.1),
                    "silver": inventoryReward("silver", weight=0.2),
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
            collectives={"team": CollectiveConfig(inventory=InventoryConfig())},
            objects={"wall": WallConfig()},
            agent=AgentConfig(
                collective="team",
                inventory=InventoryConfig(initial={"gold": 10}),
                rewards={
                    "gold": inventoryReward("gold", weight=0.1, per_tick=per_tick),
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


@pytest.mark.xfail(reason="GameValueScope.COLLECTIVE removed from C++ in GameValueConfig variant refactor")
class TestDeltaStatReward:
    """Test that delta=True on stat rewards excludes initial state."""

    def test_delta_excludes_initial_collective_deposits(self):
        """Initial collective inventory should not produce reward with delta=True.

        When a collective starts with initial resources, the deposited stat is
        non-zero from step 0. With delta=True the reward should only reflect
        changes *after* initialization.
        """
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
            collectives={
                "team": CollectiveConfig(
                    inventory=InventoryConfig(initial={"gold": 100}),
                ),
            },
            objects={"wall": WallConfig()},
            agent=AgentConfig(
                collective="team",
                rewards={
                    "deposited": reward(
                        game_stat("collective.gold.deposited", delta=True),
                        weight=1.0,
                    ),
                },
            ),
        )

        cfg = MettaGridConfig(game=game_config)
        cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=game_map)
        sim = Simulation(cfg, seed=42)
        agent = sim.agent(0)

        for _ in range(5):
            agent.set_action(Action(name="noop"))
            sim.step()

        assert agent.episode_reward == 0.0, f"delta=True should exclude initial deposits, got {agent.episode_reward}"

    def test_no_delta_excludes_initial_collective_wealth(self):
        """Initial collective wealth is not a deposit, so it never produces deposit reward."""
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
            collectives={
                "team": CollectiveConfig(
                    inventory=InventoryConfig(initial={"gold": 100}),
                ),
            },
            objects={"wall": WallConfig()},
            agent=AgentConfig(
                collective="team",
                rewards={
                    "deposited": reward(
                        game_stat("collective.gold.deposited"),
                        weight=1.0,
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

        assert agent.episode_reward == 0.0, f"Initial wealth is not a deposit, got {agent.episode_reward}"
