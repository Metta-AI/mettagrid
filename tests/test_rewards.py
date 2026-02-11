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
