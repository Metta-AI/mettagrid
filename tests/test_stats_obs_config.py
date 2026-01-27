"""Tests for StatsValue config."""

from mettagrid.config.mettagrid_c_config import convert_to_cpp_game_config
from mettagrid.config.mettagrid_config import GameConfig, MettaGridConfig
from mettagrid.config.obs_config import GlobalObsConfig, ObsConfig, StatsSource, StatsValue
from mettagrid.simulator.simulator import Simulation, Simulator
from mettagrid.test_support.map_builders import ObjectNameMapBuilder


def test_stats_source_enum():
    """Test StatsSource enum values."""
    assert StatsSource.OWN.value == "own"
    assert StatsSource.GLOBAL.value == "global"
    assert StatsSource.COLLECTIVE.value == "collective"


def test_stats_value_defaults():
    """Test StatsValue default values."""
    sv = StatsValue(name="carbon.gained")
    assert sv.name == "carbon.gained"
    assert sv.source == StatsSource.OWN
    assert sv.delta is False


def test_stats_value_with_all_fields():
    """Test StatsValue with all fields specified."""
    sv = StatsValue(name="aligned.assembler.held", source=StatsSource.COLLECTIVE, delta=True)
    assert sv.name == "aligned.assembler.held"
    assert sv.source == StatsSource.COLLECTIVE
    assert sv.delta is True


def test_global_obs_config_stats_obs_default():
    """Test GlobalObsConfig stats_obs defaults to empty list."""
    config = GlobalObsConfig()
    assert config.stats_obs == []


def test_global_obs_config_with_stats_obs():
    """Test GlobalObsConfig with stats_obs specified."""
    config = GlobalObsConfig(
        stats_obs=[
            StatsValue(name="carbon.gained"),
            StatsValue(name="tokens_written", source=StatsSource.GLOBAL),
        ]
    )
    assert len(config.stats_obs) == 2
    assert config.stats_obs[0].name == "carbon.gained"
    assert config.stats_obs[1].source == StatsSource.GLOBAL


def test_id_map_stats_obs_feature_ids():
    """Test that IdMap allocates feature IDs for stats_obs."""
    config = GameConfig(
        obs=ObsConfig(
            global_obs=GlobalObsConfig(
                stats_obs=[
                    StatsValue(name="carbon.gained", source=StatsSource.OWN),
                    StatsValue(name="tokens_written", source=StatsSource.GLOBAL, delta=True),
                ]
            )
        )
    )
    id_map = config.id_map()
    features = id_map.features()
    feature_names = [f.name for f in features]

    # Check that stats features are allocated
    assert "stat:own:carbon.gained" in feature_names
    assert "stat:global:tokens_written:delta" in feature_names

    # Check multi-token features (p1, p2, etc.)
    assert "stat:own:carbon.gained:p1" in feature_names
    assert "stat:global:tokens_written:delta:p1" in feature_names


def test_id_map_stats_obs_empty():
    """Test that IdMap works with empty stats_obs."""
    config = GameConfig(obs=ObsConfig(global_obs=GlobalObsConfig(stats_obs=[])))
    id_map = config.id_map()
    features = id_map.features()
    feature_names = [f.name for f in features]

    # No stat features should be present
    assert not any(name.startswith("stat:") for name in feature_names)


def test_cpp_conversion_stats_obs():
    """Test that stats_obs converts correctly to C++."""
    config = GameConfig(
        obs=ObsConfig(
            global_obs=GlobalObsConfig(
                stats_obs=[
                    StatsValue(name="carbon.gained", source=StatsSource.OWN),
                    StatsValue(name="tokens_written", source=StatsSource.GLOBAL, delta=True),
                ]
            )
        )
    )
    cpp_config = convert_to_cpp_game_config(config)

    assert len(cpp_config.global_obs.stats_obs) == 2

    stat0 = cpp_config.global_obs.stats_obs[0]
    assert stat0.name == "carbon.gained"
    assert stat0.delta is False
    assert stat0.feature_id > 0  # Should have a valid feature ID

    stat1 = cpp_config.global_obs.stats_obs[1]
    assert stat1.name == "tokens_written"
    assert stat1.delta is True


def test_stats_obs_in_observation():
    """Test that stats observations appear in agent observations."""
    game_config = GameConfig(
        num_agents=1,
        max_steps=10,
        obs=ObsConfig(
            global_obs=GlobalObsConfig(
                stats_obs=[
                    StatsValue(name="carbon.gained", source=StatsSource.OWN),
                ]
            )
        ),
    )

    game_map = [
        ["agent.agent"],
    ]

    cfg = MettaGridConfig(game=game_config)
    cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=game_map)

    sim = Simulation(cfg, seed=42)

    # Get agent observation
    agent = sim.agent(0)
    obs = agent.observation

    # Find stat token in observation
    stat_tokens = [t for t in obs.tokens if t.feature.name.startswith("stat:")]
    assert len(stat_tokens) >= 1, f"Expected stat tokens, got {[t.feature.name for t in obs.tokens]}"
    assert stat_tokens[0].feature.name == "stat:own:carbon.gained"

    sim.close()


def test_config_invariants_include_stats_obs():
    """Test that stats_obs is included in config invariants."""
    config = MettaGridConfig(
        game=GameConfig(
            num_agents=1,
            obs=ObsConfig(
                global_obs=GlobalObsConfig(
                    stats_obs=[
                        StatsValue(name="carbon.gained", source=StatsSource.OWN),
                    ]
                )
            ),
        )
    )

    simulator = Simulator()
    invariants = simulator._compute_config_invariants(config)

    assert "stats_obs" in invariants
    assert invariants["stats_obs"] == [("carbon.gained", "own", False)]


def test_stats_obs_tokens_present_after_step():
    """Test that stats observation tokens are present after a simulation step."""
    game_config = GameConfig(
        num_agents=1,
        max_steps=100,
        obs=ObsConfig(
            global_obs=GlobalObsConfig(
                stats_obs=[
                    StatsValue(name="carbon.gained", source=StatsSource.OWN),
                    StatsValue(name="carbon.gained", source=StatsSource.OWN, delta=True),
                ]
            )
        ),
    )

    game_map = [
        ["agent.agent"],
    ]

    cfg = MettaGridConfig(game=game_config)
    cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=game_map)

    sim = Simulation(cfg, seed=42)
    agent = sim.agent(0)

    # Initial observation - stats should be 0
    obs1 = agent.observation
    stat_tokens = [t for t in obs1.tokens if t.feature.name == "stat:own:carbon.gained"]
    assert len(stat_tokens) >= 1
    assert stat_tokens[0].value == 0  # No carbon gained yet

    # Step the simulation (no action needed for first step)
    agent.set_action("noop")
    sim.step()

    # Verify we can get observation again
    obs2 = agent.observation
    cumulative_tokens = [t for t in obs2.tokens if t.feature.name == "stat:own:carbon.gained"]
    delta_tokens = [t for t in obs2.tokens if t.feature.name == "stat:own:carbon.gained:delta"]

    # Both should exist
    assert len(cumulative_tokens) >= 1, (
        f"Expected cumulative stat tokens, got features: {[t.feature.name for t in obs2.tokens]}"
    )
    assert len(delta_tokens) >= 1, f"Expected delta stat tokens, got features: {[t.feature.name for t in obs2.tokens]}"

    sim.close()
