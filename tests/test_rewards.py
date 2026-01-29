from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    AgentConfig,
    AssemblerConfig,
    AttackActionConfig,
    ChangeVibeActionConfig,
    CollectiveConfig,
    GameConfig,
    GridObjectConfig,
    InventoryConfig,
    MettaGridConfig,
    MoveActionConfig,
    NoopActionConfig,
    ProtocolConfig,
    WallConfig,
)
from mettagrid.config.reward_config import inventoryReward, statReward
from mettagrid.simulator import Action, Simulation
from mettagrid.test_support.map_builders import ObjectNameMapBuilder
from mettagrid.test_support.orientation import Orientation

NUM_AGENTS = 1
OBS_HEIGHT = 3
OBS_WIDTH = 3
NUM_OBS_TOKENS = 100
OBS_TOKEN_SIZE = 3


def create_heart_reward_test_env(max_steps=50, num_agents=NUM_AGENTS):
    """Helper function to create a Simulation environment with heart collection for reward testing."""

    # Create a simple map with agent, assembler, and walls
    # Assembler will produce hearts that the agent can collect for rewards
    game_map = [
        ["wall", "wall", "wall", "wall", "wall", "wall"],
        ["wall", "agent.red", "empty", "assembler", "empty", "wall"],
        ["wall", "empty", "empty", "empty", "empty", "wall"],
        ["wall", "wall", "wall", "wall", "wall", "wall"],
    ]

    game_config = GameConfig(
        max_steps=max_steps,
        num_agents=num_agents,
        resource_names=["laser", "armor", "heart"],
        actions=ActionsConfig(
            noop=NoopActionConfig(enabled=True),
            move=MoveActionConfig(enabled=True),
            attack=AttackActionConfig(enabled=True, consumed_resources={"laser": 1}, defense_resources={"armor": 1}),
            change_vibe=ChangeVibeActionConfig(enabled=False, vibes=[]),
        ),
        objects={
            "wall": WallConfig(),
            "assembler": AssemblerConfig(
                name="assembler",
                protocols=[
                    # Protocol that produces 1 heart with cooldown of 5 steps
                    ProtocolConfig(input_resources={}, output_resources={"heart": 1}, cooldown=5)
                ],
            ),
        },
        agent=AgentConfig(
            inventory=InventoryConfig(default_limit=10),
            rewards={"heart": inventoryReward("heart")},
        ),
    )

    # Create MettaGridConfig wrapper
    cfg = MettaGridConfig(game=game_config)
    cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=game_map)

    return Simulation(cfg, seed=42)


def get_action_name(base_name: str, orientation: Orientation | None = None) -> str:
    """Get the action name for a given base name and orientation."""
    if orientation is None:
        return base_name
    return f"{base_name}_{orientation.name.lower()}"


class TestRewards:
    def test_step_rewards_initialization(self):
        """Test that step rewards are properly initialized to zero."""
        sim = create_heart_reward_test_env()

        # Get the agent and initial reward (should be zero before any action)
        agent = sim.agent(0)
        initial_reward = agent.step_reward

        # Rewards should be zero initially
        assert initial_reward == 0.0, f"Initial reward should be zero, got {initial_reward}"

        # Take a step with noop action
        agent.set_action(Action(name="noop"))
        sim.step()

        # Get the step reward (should still be zero for noop with no reward triggers)
        step_reward = agent.step_reward
        assert step_reward == 0.0, f"Noop step reward should be zero, got {step_reward}"

        # Check that action succeeded
        assert sim.agent(0).last_action_success, "Noop should always succeed"

    def test_heart_collection_rewards(self):
        """Test that collecting hearts generates real rewards."""
        sim = create_heart_reward_test_env()
        agent = sim.agent(0)

        # Agent starts at (1, 1), assembler is at (1, 3)
        # Move east to (1, 2) which is adjacent to the assembler
        agent.set_action(Action(name=get_action_name("move", Orientation.EAST)))
        sim.step()

        # Verify move succeeded
        assert sim.agent(0).last_action_success, "Move to assembler should succeed"

        # Wait for assembler cooldown (5 steps) to produce hearts
        for _ in range(6):
            agent.set_action(Action(name="noop"))
            sim.step()

        # Now move east again to interact with the assembler and collect heart
        agent.set_action(Action(name=get_action_name("move", Orientation.EAST)))
        sim.step()

        # Check if we got a heart in inventory (which should give a reward)
        hearts = agent.inventory.get("heart", 0)
        assert hearts > 0, f"Agent should have collected at least one heart, got {hearts}"

        # Get the step reward from when we collected the heart
        step_reward = agent.step_reward
        assert step_reward > 0, f"Step reward should be positive after collecting heart, got {step_reward}"

    def test_multiple_heart_collections(self):
        """Test collecting multiple hearts and verifying cumulative rewards."""
        sim = create_heart_reward_test_env()
        agent = sim.agent(0)

        move_east_action = get_action_name("move", Orientation.EAST)

        # Track cumulative reward
        cumulative_reward = 0.0

        # Move to assembler
        agent.set_action(Action(name=move_east_action))
        sim.step()
        cumulative_reward += agent.step_reward

        # Wait for first heart production (6 steps)
        for _ in range(6):
            agent.set_action(Action(name="noop"))
            sim.step()
            cumulative_reward += agent.step_reward

        # First collection - interact with assembler
        agent.set_action(Action(name=move_east_action))
        sim.step()
        cumulative_reward += agent.step_reward
        hearts_1 = agent.inventory.get("heart", 0)
        reward_after_first = cumulative_reward

        assert hearts_1 > 0, "First collection should give hearts"
        assert reward_after_first > 0, "First collection should give positive reward"

        # Wait for second heart production (6 more steps)
        for _ in range(6):
            agent.set_action(Action(name="noop"))
            sim.step()
            cumulative_reward += agent.step_reward

        # Second collection - interact with assembler again
        agent.set_action(Action(name=move_east_action))
        sim.step()
        cumulative_reward += agent.step_reward
        hearts_2 = agent.inventory.get("heart", 0)
        reward_after_second = cumulative_reward

        # Verify we collected more hearts
        assert hearts_2 > hearts_1, f"Should have more hearts after second collection: {hearts_2} vs {hearts_1}"

        # Verify rewards accumulated
        assert reward_after_second > reward_after_first, (
            f"Total reward should accumulate: {reward_after_second} vs {reward_after_first}"
        )


class TestRewardWithMaxCap:
    """Test rewards with max cap functionality."""

    def test_inventory_reward_respects_max_cap(self):
        """Test that inventory rewards are capped at the max value."""
        game_map = [
            ["wall", "wall", "wall", "wall", "wall", "wall"],
            ["wall", "agent.red", "empty", "assembler", "empty", "wall"],
            ["wall", "empty", "empty", "empty", "empty", "wall"],
            ["wall", "wall", "wall", "wall", "wall", "wall"],
        ]

        game_config = GameConfig(
            max_steps=100,
            num_agents=1,
            resource_names=["heart"],
            actions=ActionsConfig(
                noop=NoopActionConfig(enabled=True),
                move=MoveActionConfig(enabled=True),
            ),
            objects={
                "wall": WallConfig(),
                "assembler": AssemblerConfig(
                    name="assembler",
                    protocols=[ProtocolConfig(input_resources={}, output_resources={"heart": 10}, cooldown=1)],
                ),
            },
            agent=AgentConfig(
                inventory=InventoryConfig(default_limit=100),
                # Cap reward at 5.0, even if hearts * weight would be higher
                rewards={"heart": inventoryReward("heart", weight=1.0, max=5.0)},
            ),
        )

        cfg = MettaGridConfig(game=game_config)
        cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=game_map)
        sim = Simulation(cfg, seed=42)
        agent = sim.agent(0)

        # Move to assembler and collect many hearts
        agent.set_action(Action(name=get_action_name("move", Orientation.EAST)))
        sim.step()

        # Wait for assembler to produce hearts
        for _ in range(5):
            agent.set_action(Action(name="noop"))
            sim.step()

        # Collect hearts
        agent.set_action(Action(name=get_action_name("move", Orientation.EAST)))
        sim.step()

        # Episode reward should be capped at 5.0
        # Even though agent has many hearts, reward is capped
        assert agent.episode_reward <= 5.0, f"Reward should be capped at 5.0, got {agent.episode_reward}"
        # But should have some reward
        assert agent.episode_reward > 0, "Should have positive reward"


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
