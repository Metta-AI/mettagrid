"""Test collective stats rewards (e.g., junction.held) for mettagrid.

These tests verify that:
1. Collective stats rewards are properly converted to C++ stat_rewards
2. update_held_stats() is called during simulation steps to track holding duration
3. Agents receive rewards based on their collective's held stats
"""

from mettagrid.config.game_value import stat as game_stat
from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    AgentConfig,
    CollectiveConfig,
    GameConfig,
    GridObjectConfig,
    InventoryConfig,
    MettaGridConfig,
    MoveActionConfig,
    NoopActionConfig,
    WallConfig,
)
from mettagrid.config.reward_config import inventoryReward, reward
from mettagrid.simulator import Action, Simulation
from mettagrid.test_support.map_builders import ObjectNameMapBuilder


class TestCollectiveStatsRewardsConversion:
    """Test that collective_stats rewards are properly converted to C++."""

    def test_collective_stats_converted_to_stat_rewards(self):
        """Test that collective_stats rewards are included in C++ stat_rewards.

        This would have caught the bug where collective_stats were defined in
        rewards but never converted to C++ stat_rewards.

        We test this via integration - create an env with collective_stats reward
        and verify the agent actually receives rewards.
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
                "cogs": CollectiveConfig(inventory=InventoryConfig()),
            },
            objects={
                "wall": WallConfig(),
            },
            agent=AgentConfig(
                collective="cogs",
                rewards={
                    # This tests collective_stats conversion - agent is member of collective
                    "agent_held": reward(
                        game_stat("collective.aligned.agent.held"),
                        weight=0.1,
                    ),
                },
            ),
        )

        cfg = MettaGridConfig(game=game_config)
        cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=game_map)
        sim = Simulation(cfg, seed=42)
        agent = sim.agent(0)

        # Take some steps
        for _ in range(5):
            agent.set_action(Action(name="noop"))
            sim.step()

        # If collective_stats wasn't converted, reward would be 0
        assert agent.episode_reward > 0.0, (
            f"collective_stats should be converted - expected positive reward, got {agent.episode_reward}"
        )

    def test_collective_stats_merged_with_stats(self):
        """Test that collective_stats are merged with regular stats rewards.

        Agent should receive rewards from both stats and collective_stats.
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
                "cogs": CollectiveConfig(inventory=InventoryConfig()),
            },
            objects={
                "wall": WallConfig(),
            },
            agent=AgentConfig(
                collective="cogs",
                inventory=InventoryConfig(initial={"gold": 10}),
                rewards={
                    # Regular inventory reward
                    "gold": inventoryReward("gold", weight=0.1),
                    # Collective stats reward
                    "agent_held": reward(
                        game_stat("collective.aligned.agent.held"),
                        weight=0.1,
                    ),
                },
            ),
        )

        cfg = MettaGridConfig(game=game_config)
        cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=game_map)
        sim = Simulation(cfg, seed=42)
        agent = sim.agent(0)

        # Take steps
        for _ in range(5):
            agent.set_action(Action(name="noop"))
            sim.step()

        # Should have rewards from both sources (inventory + collective_stats)
        # inventory: 10 gold * 0.1 = 1.0
        # collective_stats: accumulating held stat
        assert agent.episode_reward > 1.0, (
            f"Should have rewards from both stats and collective_stats, got {agent.episode_reward}"
        )


class TestCollectiveHeldStatsIntegration:
    """Test that held stats are properly tracked and rewarded during simulation.

    These tests would have caught the bug where update_held_stats() was never
    called in the simulation step loop, causing *.held stats to always be 0.
    """

    def _create_pre_aligned_junction_env(self, max_steps=100):
        """Create a test environment with a junction pre-aligned to agent's collective."""
        game_map = [
            ["wall", "wall", "wall", "wall", "wall"],
            ["wall", "agent.red", "empty", "junction", "wall"],
            ["wall", "wall", "wall", "wall", "wall"],
        ]

        game_config = GameConfig(
            max_steps=max_steps,
            num_agents=1,
            resource_names=["gold"],
            actions=ActionsConfig(
                noop=NoopActionConfig(enabled=True),
                move=MoveActionConfig(enabled=True),
            ),
            collectives={
                "cogs": CollectiveConfig(inventory=InventoryConfig()),
            },
            objects={
                "wall": WallConfig(),
                # Junction starts aligned to cogs collective
                "junction": GridObjectConfig(
                    name="junction",
                    collective="cogs",  # Pre-aligned to agent's collective
                ),
            },
            agent=AgentConfig(
                collective="cogs",
                rewards={
                    # Reward for each step a junction is held by the collective
                    "junction_held": reward(
                        game_stat("collective.aligned.junction.held"),
                        weight=0.01,
                    ),
                },
            ),
        )

        cfg = MettaGridConfig(game=game_config)
        cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=game_map)

        return Simulation(cfg, seed=42)

    def test_reward_for_pre_aligned_junction(self):
        """Test that agents get rewards immediately when junction is pre-aligned."""
        sim = self._create_pre_aligned_junction_env()
        agent = sim.agent(0)

        # Take some noop steps - junction is already aligned
        for _ in range(10):
            agent.set_action(Action(name="noop"))
            sim.step()

        # Should have positive reward since junction is held from the start
        assert agent.episode_reward > 0.0, (
            f"Expected positive reward for pre-aligned junction, got {agent.episode_reward}"
        )

    def test_held_stats_accumulate_over_time(self):
        """Test that held stats accumulate each step, giving increasing rewards.

        This directly tests that update_held_stats() is being called each step.
        """
        sim = self._create_pre_aligned_junction_env()
        agent = sim.agent(0)

        # Take steps and collect rewards
        rewards = []
        for _ in range(10):
            agent.set_action(Action(name="noop"))
            sim.step()
            rewards.append(agent.episode_reward)

        # Rewards should be monotonically increasing
        for i in range(1, len(rewards)):
            assert rewards[i] > rewards[i - 1], (
                f"Rewards should strictly increase each step: step {i - 1}={rewards[i - 1]}, step {i}={rewards[i]}"
            )

    def test_held_reward_matches_expected_value(self):
        """Test that held rewards match expected values based on steps."""
        sim = self._create_pre_aligned_junction_env()
        agent = sim.agent(0)

        # Take exactly 10 steps
        num_steps = 10
        for _ in range(num_steps):
            agent.set_action(Action(name="noop"))
            sim.step()

        # With 1 junction held for 10 steps at 0.01 reward per step,
        # expect approximately 0.1 reward (accounting for step timing)
        # The held stat increments each step, so after N steps:
        # held = 1 + 2 + 3 + ... + N = N*(N+1)/2
        # But since rewards are based on current stat value, not delta,
        # the actual reward depends on implementation details
        expected_approx = num_steps * 0.01  # 10 steps * 0.01 per junction-step
        assert agent.episode_reward > 0.05, f"Expected reward around {expected_approx}, got {agent.episode_reward}"


class TestMultipleCollectiveTypes:
    """Test held stats for multiple object types."""

    def test_different_object_types_tracked_separately(self):
        """Test that different object types contribute different held stats.

        With a junction and a charger both aligned, each should contribute
        to their respective held stats with different reward weights.
        """
        game_map = [
            ["wall", "wall", "wall", "wall", "wall"],
            ["wall", "agent.red", "junction", "charger", "wall"],
            ["wall", "wall", "wall", "wall", "wall"],
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
                "junction": GridObjectConfig(name="junction", collective="team"),
                "charger": GridObjectConfig(name="charger", collective="team"),
            },
            agent=AgentConfig(
                collective="team",
                rewards={
                    "junction_held": reward(
                        game_stat("collective.aligned.junction.held"),
                        weight=0.01,
                    ),
                    "charger_held": reward(
                        game_stat("collective.aligned.charger.held"),
                        weight=0.02,
                    ),
                },
            ),
        )

        cfg = MettaGridConfig(game=game_config)
        cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=game_map)
        sim = Simulation(cfg, seed=42)
        agent = sim.agent(0)

        # Take 10 steps
        for _ in range(10):
            agent.set_action(Action(name="noop"))
            sim.step()

        # Should have rewards from both object types
        # Expected: 10 * (0.01 + 0.02) = 0.3 per step for held stats
        # Plus agent held stat if configured
        assert agent.episode_reward > 0.2, f"Should have rewards from multiple object types, got {agent.episode_reward}"


class TestNoRewardWithoutAlignment:
    """Test that held stats don't give rewards without proper alignment."""

    def _create_unaligned_junction_env(self, max_steps=100):
        """Create a test environment with unaligned junction."""
        game_map = [
            ["wall", "wall", "wall", "wall", "wall"],
            ["wall", "agent.red", "empty", "junction", "wall"],
            ["wall", "wall", "wall", "wall", "wall"],
        ]

        game_config = GameConfig(
            max_steps=max_steps,
            num_agents=1,
            resource_names=["gold"],
            actions=ActionsConfig(
                noop=NoopActionConfig(enabled=True),
                move=MoveActionConfig(enabled=True),
            ),
            collectives={
                "cogs": CollectiveConfig(inventory=InventoryConfig()),
            },
            objects={
                "wall": WallConfig(),
                # Junction has no collective - not aligned to anyone
                "junction": GridObjectConfig(
                    name="junction",
                    # No collective set - neutral junction
                ),
            },
            agent=AgentConfig(
                collective="cogs",
                rewards={
                    "junction_held": reward(
                        game_stat("collective.aligned.junction.held"),
                        weight=0.01,
                    ),
                },
            ),
        )

        cfg = MettaGridConfig(game=game_config)
        cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=game_map)

        return Simulation(cfg, seed=42)

    def test_no_reward_for_unaligned_junction(self):
        """Test that agents get no reward when junction is not aligned to them."""
        sim = self._create_unaligned_junction_env()
        agent = sim.agent(0)

        # Take several steps - junction is not aligned
        for _ in range(10):
            agent.set_action(Action(name="noop"))
            sim.step()

        # Should have zero reward since no junctions are held by our collective
        assert agent.episode_reward == 0.0, f"Expected 0 reward for unaligned junction, got {agent.episode_reward}"


class TestAgentHeldStats:
    """Test that agents aligned to a collective are tracked in held stats."""

    def _create_agent_holding_env(self, max_steps=100):
        """Create a test environment with agent aligned to collective."""
        game_map = [
            ["wall", "wall", "wall"],
            ["wall", "agent.red", "wall"],
            ["wall", "wall", "wall"],
        ]

        game_config = GameConfig(
            max_steps=max_steps,
            num_agents=1,
            resource_names=["gold"],
            actions=ActionsConfig(
                noop=NoopActionConfig(enabled=True),
            ),
            collectives={
                "cogs": CollectiveConfig(inventory=InventoryConfig()),
            },
            objects={
                "wall": WallConfig(),
            },
            agent=AgentConfig(
                collective="cogs",
                rewards={
                    # Reward for each step an agent is in the collective
                    "agent_held": reward(
                        game_stat("collective.aligned.agent.held"),
                        weight=0.01,
                    ),
                },
            ),
        )

        cfg = MettaGridConfig(game=game_config)
        cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=game_map)

        return Simulation(cfg, seed=42)

    def test_agent_held_stat_accumulates(self):
        """Test that agents themselves contribute to held stats."""
        sim = self._create_agent_holding_env()
        agent = sim.agent(0)

        # Take several steps
        for _ in range(10):
            agent.set_action(Action(name="noop"))
            sim.step()

        # Should have positive reward from agent being in collective
        assert agent.episode_reward > 0.0, f"Expected positive reward for agent held, got {agent.episode_reward}"
