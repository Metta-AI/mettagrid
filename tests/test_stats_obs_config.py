"""Tests for StatValue config."""

from mettagrid.config.game_value import Scope, StatValue
from mettagrid.config.mettagrid_c_config import convert_to_cpp_game_config
from mettagrid.config.mettagrid_config import GameConfig, MettaGridConfig
from mettagrid.config.obs_config import GlobalObsConfig, ObsConfig
from mettagrid.simulator.simulator import Simulation, Simulator
from mettagrid.test_support.map_builders import ObjectNameMapBuilder


def test_scope_enum():
    """Test Scope enum values."""
    assert Scope.AGENT.value == "agent"
    assert Scope.GAME.value == "game"
    assert Scope.COLLECTIVE.value == "collective"


def test_stat_value_defaults():
    """Test StatValue default values."""
    sv = StatValue(name="carbon.gained")
    assert sv.name == "carbon.gained"
    assert sv.scope == Scope.AGENT
    assert sv.delta is False


def test_stat_value_with_all_fields():
    """Test StatValue with all fields specified."""
    sv = StatValue(name="aligned.hub.held", scope=Scope.COLLECTIVE, delta=True)
    assert sv.name == "aligned.hub.held"
    assert sv.scope == Scope.COLLECTIVE
    assert sv.delta is True


def test_global_obs_config_obs_default():
    """Test GlobalObsConfig obs defaults to empty list."""
    config = GlobalObsConfig()
    assert config.obs == []


def test_global_obs_config_with_obs():
    """Test GlobalObsConfig with obs specified."""
    config = GlobalObsConfig(
        obs=[
            StatValue(name="carbon.gained"),
            StatValue(name="tokens_written", scope=Scope.GAME),
        ]
    )
    assert len(config.obs) == 2
    assert config.obs[0].name == "carbon.gained"
    assert config.obs[1].scope == Scope.GAME


def test_id_map_obs_feature_ids():
    """Test that IdMap allocates feature IDs for obs."""
    config = GameConfig(
        obs=ObsConfig(
            global_obs=GlobalObsConfig(
                obs=[
                    StatValue(name="carbon.gained", scope=Scope.AGENT),
                    StatValue(name="tokens_written", scope=Scope.GAME, delta=True),
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


def test_id_map_obs_empty():
    """Test that IdMap works with empty obs."""
    config = GameConfig(obs=ObsConfig(global_obs=GlobalObsConfig(obs=[])))
    id_map = config.id_map()
    features = id_map.features()
    feature_names = [f.name for f in features]

    # No stat features should be present
    assert not any(name.startswith("stat:") for name in feature_names)


def test_cpp_conversion_obs():
    """Test that obs converts correctly to C++."""
    config = GameConfig(
        obs=ObsConfig(
            global_obs=GlobalObsConfig(
                obs=[
                    StatValue(name="carbon.gained", scope=Scope.AGENT),
                    StatValue(name="tokens_written", scope=Scope.GAME, delta=True),
                ]
            )
        )
    )
    cpp_config = convert_to_cpp_game_config(config)

    assert len(cpp_config.global_obs.obs) == 2

    obs0 = cpp_config.global_obs.obs[0]
    assert obs0.value.stat_name == "carbon.gained"
    assert obs0.value.delta is False
    assert obs0.feature_id > 0  # Should have a valid feature ID

    obs1 = cpp_config.global_obs.obs[1]
    assert obs1.value.stat_name == "tokens_written"
    assert obs1.value.delta is True


def test_obs_in_observation():
    """Test that stats observations appear in agent observations."""
    game_config = GameConfig(
        num_agents=1,
        max_steps=10,
        obs=ObsConfig(
            global_obs=GlobalObsConfig(
                obs=[
                    StatValue(name="carbon.gained", scope=Scope.AGENT),
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


def test_config_invariants_include_obs():
    """Test that obs is included in config invariants."""
    config = MettaGridConfig(
        game=GameConfig(
            num_agents=1,
            obs=ObsConfig(
                global_obs=GlobalObsConfig(
                    obs=[
                        StatValue(name="carbon.gained", scope=Scope.AGENT),
                    ]
                )
            ),
        )
    )

    simulator = Simulator()
    invariants = simulator._compute_config_invariants(config)

    assert "obs_values" in invariants
    assert len(invariants["obs_values"]) == 1


def test_obs_tokens_present_after_step():
    """Test that stats observation tokens are present after a simulation step."""
    game_config = GameConfig(
        num_agents=1,
        max_steps=100,
        obs=ObsConfig(
            global_obs=GlobalObsConfig(
                obs=[
                    StatValue(name="carbon.gained", scope=Scope.AGENT),
                    StatValue(name="carbon.gained", scope=Scope.AGENT, delta=True),
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
