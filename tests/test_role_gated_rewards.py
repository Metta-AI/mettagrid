import pytest

from mettagrid.config.action_config import ActionsConfig, NoopActionConfig
from mettagrid.config.mettagrid_config import GameConfig, MettaGridConfig, ObsConfig
from mettagrid.config.reward_config import reward, stat
from mettagrid.map_builder.random_map import RandomMapBuilder
from mettagrid.simulator import Simulation


def test_role_gated_reward_entries_apply_only_to_matching_agent_mod4() -> None:
    # Use a stat that increments for every agent that successfully noops.
    # The reward entry is role-gated to "miner" (agent_id % 4 == 0).
    cfg = MettaGridConfig(
        game=GameConfig(
            num_agents=4,
            max_steps=10,
            obs=ObsConfig(width=5, height=5, num_tokens=50),
            actions=ActionsConfig(noop=NoopActionConfig()),
            map_builder=RandomMapBuilder.Config(seed=0, agents=4, width=10, height=10),
        )
    )
    cfg.game.agent.rewards = {
        "role:miner:test_noop_success": reward(stat("action.noop.success"), weight=1.0),
    }

    sim = Simulation(cfg)
    for agent_id in range(4):
        sim.agent(agent_id).set_action("noop")
    sim.step()

    rewards = sim._c_sim.rewards().copy()
    assert rewards[0] == 1.0
    assert rewards[1] == 0.0
    assert rewards[2] == 0.0
    assert rewards[3] == 0.0


def test_role_gated_rewards_respect_role_order_override() -> None:
    # Make every agent a miner via role_order, then a miner-gated reward should apply to all agents.
    cfg = MettaGridConfig(
        game=GameConfig(
            num_agents=4,
            max_steps=10,
            obs=ObsConfig(width=5, height=5, num_tokens=50),
            actions=ActionsConfig(noop=NoopActionConfig()),
            map_builder=RandomMapBuilder.Config(seed=0, agents=4, width=10, height=10),
        )
    )
    cfg.game.agent.role_order = ["miner"]
    cfg.game.agent.rewards = {
        "role:miner:test_noop_success": reward(stat("action.noop.success"), weight=1.0),
    }

    sim = Simulation(cfg)
    for agent_id in range(4):
        sim.agent(agent_id).set_action("noop")
    sim.step()

    rewards = sim._c_sim.rewards().copy()
    assert rewards[0] == 1.0
    assert rewards[1] == 1.0
    assert rewards[2] == 1.0
    assert rewards[3] == 1.0


def test_role_gated_rewards_scale_by_soft_role_weights() -> None:
    # Soft roles: agent2 is 50% miner + 50% aligner. A miner-prefixed reward should apply at 128/255 scale.
    cfg = MettaGridConfig(
        game=GameConfig(
            num_agents=4,
            max_steps=10,
            obs=ObsConfig(width=5, height=5, num_tokens=50),
            actions=ActionsConfig(noop=NoopActionConfig()),
            map_builder=RandomMapBuilder.Config(seed=0, agents=4, width=10, height=10),
        )
    )
    cfg.game.agent.role_mix_order = [
        {"miner": 255},
        {"aligner": 255},
        {"miner": 128, "aligner": 128},
        {"scout": 255},
    ]
    cfg.game.agent.rewards = {
        "role:miner:test_noop_success": reward(stat("action.noop.success"), weight=1.0),
    }

    sim = Simulation(cfg)
    for agent_id in range(4):
        sim.agent(agent_id).set_action("noop")
    sim.step()

    rewards = sim._c_sim.rewards().copy()
    assert rewards[0] == 1.0
    assert rewards[1] == 0.0
    assert rewards[2] == pytest.approx(128.0 / 255.0)
    assert rewards[3] == 0.0


@pytest.mark.parametrize(
    "reward_key",
    [
        "role:miner",
        "role:",
        "role::test_noop_success",
        "role:miner:",
    ],
)
def test_role_gated_reward_keys_require_full_prefix_format(reward_key: str) -> None:
    cfg = MettaGridConfig(
        game=GameConfig(
            num_agents=4,
            max_steps=1,
            obs=ObsConfig(width=5, height=5, num_tokens=50),
            actions=ActionsConfig(noop=NoopActionConfig()),
            map_builder=RandomMapBuilder.Config(seed=0, agents=4, width=10, height=10),
        )
    )
    cfg.game.agent.rewards = {
        reward_key: reward(stat("action.noop.success"), weight=1.0),
    }

    with pytest.raises(ValueError, match="Invalid role-gated reward key"):
        Simulation(cfg)
