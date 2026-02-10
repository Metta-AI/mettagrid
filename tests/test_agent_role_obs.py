import pytest

from mettagrid.config.action_config import ActionsConfig, NoopActionConfig
from mettagrid.config.mettagrid_config import GameConfig, MettaGridConfig, ObsConfig
from mettagrid.map_builder.random_map import RandomMapBuilder
from mettagrid.simulator import Location, Simulation
from mettagrid.test_support import ObservationHelper


def _make_sim(*, num_agents: int) -> Simulation:
    cfg = MettaGridConfig(
        game=GameConfig(
            num_agents=num_agents,
            max_steps=10,
            obs=ObsConfig(width=11, height=11, num_tokens=100),
            actions=ActionsConfig(noop=NoopActionConfig()),
            map_builder=RandomMapBuilder.Config(seed=0, agents=num_agents, width=20, height=20),
        )
    )
    return Simulation(cfg)


@pytest.mark.parametrize("num_agents", [1, 4, 8])
def test_agent_role_token_is_centered_and_wraps_mod4(num_agents: int) -> None:
    sim = _make_sim(num_agents=num_agents)

    for agent_id in range(num_agents):
        sim.agent(agent_id).set_action("noop")
    sim.step()

    helper = ObservationHelper()
    obs = sim._c_sim.observations()
    role_fid = sim.config.game.id_map().feature_id("agent:role")

    center = Location(row=sim.config.game.obs.height // 2, col=sim.config.game.obs.width // 2)
    for agent_id in range(num_agents):
        values = helper.find_token_values(obs[agent_id], location=center, feature_id=role_fid, is_global=False)
        assert len(values) == 1
        assert int(values[0]) == agent_id % 4


def test_agent_role_token_respects_role_order_override() -> None:
    cfg = MettaGridConfig(
        game=GameConfig(
            num_agents=4,
            max_steps=10,
            obs=ObsConfig(width=11, height=11, num_tokens=100),
            actions=ActionsConfig(noop=NoopActionConfig()),
            map_builder=RandomMapBuilder.Config(seed=0, agents=4, width=20, height=20),
        )
    )
    # Override role assignment: make everyone a "miner" (role id 0).
    cfg.game.agent.role_order = ["miner"]
    sim = Simulation(cfg)

    for agent_id in range(4):
        sim.agent(agent_id).set_action("noop")
    sim.step()

    helper = ObservationHelper()
    obs = sim._c_sim.observations()
    role_fid = sim.config.game.id_map().feature_id("agent:role")
    center = Location(row=sim.config.game.obs.height // 2, col=sim.config.game.obs.width // 2)
    for agent_id in range(4):
        values = helper.find_token_values(obs[agent_id], location=center, feature_id=role_fid, is_global=False)
        assert len(values) == 1
        assert int(values[0]) == 0


def test_soft_role_tokens_emit_multiple_weights_at_center() -> None:
    cfg = MettaGridConfig(
        game=GameConfig(
            num_agents=4,
            max_steps=10,
            obs=ObsConfig(width=11, height=11, num_tokens=120),
            actions=ActionsConfig(noop=NoopActionConfig()),
            map_builder=RandomMapBuilder.Config(seed=0, agents=4, width=20, height=20),
        )
    )
    # Per-agent-by-index specs:
    # agent0: miner 1.0
    # agent1: aligner 1.0
    # agent2: miner 0.5 + aligner 0.5
    # agent3: scout 1.0
    cfg.game.agent.role_mix_order = [
        {"miner": 255},
        {"aligner": 255},
        {"miner": 128, "aligner": 128},
        {"scout": 255},
    ]
    sim = Simulation(cfg)

    for agent_id in range(4):
        sim.agent(agent_id).set_action("noop")
    sim.step()

    helper = ObservationHelper()
    obs = sim._c_sim.observations()
    center = Location(row=sim.config.game.obs.height // 2, col=sim.config.game.obs.width // 2)

    fid_miner = sim.config.game.id_map().feature_id("agent:role:miner")
    fid_aligner = sim.config.game.id_map().feature_id("agent:role:aligner")
    fid_scout = sim.config.game.id_map().feature_id("agent:role:scout")

    # agent0: miner only
    assert helper.find_token_values(obs[0], location=center, feature_id=fid_miner, is_global=False).tolist() == [255]
    assert helper.find_token_values(obs[0], location=center, feature_id=fid_aligner, is_global=False).tolist() == []

    # agent1: aligner only
    assert helper.find_token_values(obs[1], location=center, feature_id=fid_aligner, is_global=False).tolist() == [255]
    assert helper.find_token_values(obs[1], location=center, feature_id=fid_miner, is_global=False).tolist() == []

    # agent2: miner + aligner 50/50
    assert helper.find_token_values(obs[2], location=center, feature_id=fid_miner, is_global=False).tolist() == [128]
    assert helper.find_token_values(obs[2], location=center, feature_id=fid_aligner, is_global=False).tolist() == [128]

    # agent3: scout only
    assert helper.find_token_values(obs[3], location=center, feature_id=fid_scout, is_global=False).tolist() == [255]
