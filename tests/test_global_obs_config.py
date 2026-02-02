"""Test global observation configuration functionality."""

from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    AgentConfig,
    GameConfig,
    GlobalObsConfig,
    InventoryConfig,
    MettaGridConfig,
    MoveActionConfig,
    NoopActionConfig,
    ObsConfig,
    WallConfig,
)
from mettagrid.mettagrid_c import PackedCoordinate
from mettagrid.simulator import Action, Simulation
from mettagrid.test_support import ObservationHelper
from mettagrid.test_support.map_builders import ObjectNameMapBuilder


def create_test_sim(global_obs_config: dict[str, bool]) -> Simulation:
    """Create test simulation with specified global_obs configuration."""
    game_config = GameConfig(
        num_agents=2,
        obs=ObsConfig(width=11, height=11, num_tokens=100, global_obs=GlobalObsConfig(**global_obs_config)),
        max_steps=100,
        resource_names=["item1", "item2"],
        agent=AgentConfig(inventory=InventoryConfig(default_limit=10), freeze_duration=0),
        actions=ActionsConfig(noop=NoopActionConfig(enabled=True), move=MoveActionConfig(enabled=True)),
        objects={"wall": WallConfig()},
    )

    game_map = [
        ["wall", "wall", "wall", "wall"],
        ["wall", "agent.agent", "agent.agent", "wall"],
        ["wall", "wall", "wall", "wall"],
    ]

    cfg = MettaGridConfig(game=game_config)
    cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=game_map)

    sim = Simulation(cfg, seed=42)

    # Step once to populate observations
    for i in range(sim.num_agents):
        sim.agent(i).set_action(Action(name="noop"))
    sim.step()

    return sim


def test_all_global_tokens_enabled():
    """Test that all global tokens are present when enabled."""
    global_obs = {"episode_completion_pct": True, "last_action": True, "last_reward": True}

    sim = create_test_sim(global_obs)

    # Check both agents have all global observation tokens
    for i in range(sim.num_agents):
        agent = sim.agent(i)
        global_obs_data = agent.global_observations

        assert "episode_completion_pct" in global_obs_data, "Should have episode_completion_pct"
        assert "last_action" in global_obs_data, "Should have last_action"
        assert "last_reward" in global_obs_data, "Should have last_reward"


def test_episode_completion_disabled():
    """Test that episode completion token is not present when disabled."""
    global_obs = {"episode_completion_pct": False, "last_action": True, "last_reward": True}

    sim = create_test_sim(global_obs)

    # Check that agents have last_action and last_reward but NOT episode_completion_pct
    for i in range(sim.num_agents):
        agent = sim.agent(i)
        global_obs_data = agent.global_observations

        assert "episode_completion_pct" not in global_obs_data, "Should NOT have episode_completion_pct when disabled"
        assert "last_action" in global_obs_data, "Should have last_action"
        assert "last_reward" in global_obs_data, "Should have last_reward"


def test_last_action_disabled():
    """Test that last action tokens are not present when disabled."""
    global_obs = {"episode_completion_pct": True, "last_action": False, "last_reward": True}

    sim = create_test_sim(global_obs)

    # Check that agents have episode_completion_pct and last_reward but NOT last_action
    for i in range(sim.num_agents):
        agent = sim.agent(i)
        global_obs_data = agent.global_observations

        assert "episode_completion_pct" in global_obs_data, "Should have episode_completion_pct"
        assert "last_action" not in global_obs_data, "Should NOT have last_action when disabled"
        assert "last_reward" in global_obs_data, "Should have last_reward"


def test_all_global_tokens_disabled():
    """Test that no global tokens are present when all disabled."""
    global_obs = {"episode_completion_pct": False, "last_action": False, "last_reward": False}

    sim = create_test_sim(global_obs)

    # Check that agents have NO global observation tokens
    for i in range(sim.num_agents):
        agent = sim.agent(i)
        global_obs_data = agent.global_observations

        assert "episode_completion_pct" not in global_obs_data, "Should NOT have episode_completion_pct"
        assert "last_action" not in global_obs_data, "Should NOT have last_action"
        assert "last_reward" not in global_obs_data, "Should NOT have last_reward"

        # Global obs dict should be empty or only have other non-global tokens
        assert len(global_obs_data) == 0, f"Should have no global tokens, got {list(global_obs_data.keys())}"


def test_global_obs_default_values():
    """Test that global_obs uses default values when not specified."""
    # Test with no global_obs specified - should use defaults (all True)
    game_config = GameConfig(
        num_agents=1,
        obs=ObsConfig(width=11, height=11, num_tokens=100),
        max_steps=100,
        resource_names=["item1"],
        # No global_obs specified - should use defaults
        agent=AgentConfig(inventory=InventoryConfig(default_limit=10), freeze_duration=0),
        actions=ActionsConfig(noop=NoopActionConfig(enabled=True)),
        objects={"wall": WallConfig()},
    )

    game_map = [["agent.agent"]]

    cfg = MettaGridConfig(game=game_config)
    cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=game_map)

    sim = Simulation(cfg, seed=42)

    # Step once to populate observations
    sim.agent(0).set_action(Action(name="noop"))
    sim.step()

    # Should have all global tokens by default
    agent = sim.agent(0)
    global_obs_data = agent.global_observations

    assert "episode_completion_pct" in global_obs_data, "Should have episode_completion_pct by default"
    assert "last_action" in global_obs_data, "Should have last_action by default"
    assert "last_reward" in global_obs_data, "Should have last_reward by default"


def test_global_tokens_use_global_location():
    """Test that global tokens are emitted at GLOBAL_LOCATION (0xFE), not center."""
    global_obs = {"episode_completion_pct": True, "last_action": True, "last_reward": True}
    sim = create_test_sim(global_obs)
    helper = ObservationHelper()

    obs = sim._c_sim.observations()

    for i in range(sim.num_agents):
        # All global tokens should be at GLOBAL_LOCATION (0xFE)
        global_tokens = helper.find_global_tokens(obs[i])
        assert global_tokens.shape[0] == 3, f"Expected 3 global tokens, got {global_tokens.shape[0]}"

        # Verify all global tokens have location 0xFE
        for token in global_tokens:
            assert token[0] == PackedCoordinate.GLOBAL_LOCATION, f"Global token should be at 0xFE, got {hex(token[0])}"


def test_global_tokens_distinct_from_center():
    """Test that global tokens are NOT at center position."""
    global_obs = {"episode_completion_pct": True, "last_action": True, "last_reward": True}
    sim = create_test_sim(global_obs)
    helper = ObservationHelper()

    obs = sim._c_sim.observations()
    center_row = sim.config.game.obs.height // 2
    center_col = sim.config.game.obs.width // 2
    center_packed = PackedCoordinate.pack(center_row, center_col)

    for i in range(sim.num_agents):
        # Global tokens should NOT be at center
        global_tokens = helper.find_global_tokens(obs[i])
        for token in global_tokens:
            assert token[0] != center_packed, "Global tokens should not be at center position"


def test_global_observation_tokens_method():
    """Test the global_observation_tokens() method on SimulationAgent."""
    global_obs = {"episode_completion_pct": True, "last_action": True, "last_reward": True}
    sim = create_test_sim(global_obs)

    for i in range(sim.num_agents):
        agent = sim.agent(i)
        global_tokens = agent.global_observation_tokens()

        # Should have 3 global tokens
        assert len(global_tokens) == 3, f"Expected 3 global tokens, got {len(global_tokens)}"

        # All tokens should be marked as global
        for token in global_tokens:
            assert token.is_global, "Token from global_observation_tokens() should be global"
            assert token.location is None, "Global token should have None location"


def test_self_observation_excludes_global_tokens():
    """Test that self_observation() does NOT include global tokens."""
    global_obs = {"episode_completion_pct": True, "last_action": True, "last_reward": True}
    sim = create_test_sim(global_obs)

    for i in range(sim.num_agents):
        agent = sim.agent(i)
        self_tokens = agent.self_observation()

        # None of the self_observation tokens should be global
        for token in self_tokens:
            assert not token.is_global, f"self_observation() should not include global tokens, got {token.feature.name}"


def test_observation_helper_is_global_filter():
    """Test ObservationHelper find_tokens with is_global filter."""
    global_obs = {"episode_completion_pct": True, "last_action": True, "last_reward": True}
    sim = create_test_sim(global_obs)
    helper = ObservationHelper()

    obs = sim._c_sim.observations()

    for i in range(sim.num_agents):
        # Find only global tokens
        global_only = helper.find_tokens(obs[i], is_global=True)
        assert global_only.shape[0] == 3, "Expected 3 global tokens with is_global=True"

        # Find only non-global tokens (spatial) - note: this doesn't filter empty tokens
        spatial_only = helper.find_tokens(obs[i], is_global=False)
        non_empty_spatial = [t for t in spatial_only if t[0] != 0xFF]
        for token in non_empty_spatial:
            assert token[0] != PackedCoordinate.GLOBAL_LOCATION, "is_global=False should exclude global tokens"


def test_local_position_tokens_are_global():
    """Test that local position tokens (lp:north, etc.) are at GLOBAL_LOCATION."""
    global_obs = {"episode_completion_pct": False, "last_action": False, "last_reward": False, "local_position": True}
    sim = create_test_sim(global_obs)
    helper = ObservationHelper()

    # Get feature IDs for local position features
    id_map = sim.config.game.id_map()
    lp_feature_ids = []
    for name in ["lp:north", "lp:south", "lp:east", "lp:west"]:
        try:
            lp_feature_ids.append(id_map.feature_id(name))
        except KeyError:
            pass  # Feature may not exist if agent hasn't moved

    obs = sim._c_sim.observations()

    for i in range(sim.num_agents):
        global_tokens = helper.find_global_tokens(obs[i])

        # Any local position tokens should be global
        for token in global_tokens:
            if token[1] in lp_feature_ids:
                assert token[0] == PackedCoordinate.GLOBAL_LOCATION, "Local position token should be at GLOBAL_LOCATION"
