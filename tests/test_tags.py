# Test tag system functionality for mettagrid
import pytest

from mettagrid.config.mettagrid_c_config import convert_to_cpp_game_config
from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    AgentConfig,
    GameConfig,
    MettaGridConfig,
    MoveActionConfig,
    NoopActionConfig,
    ObsConfig,
    WallConfig,
)
from mettagrid.config.tag import Tag, typeTag
from mettagrid.map_builder.ascii import AsciiMapBuilder
from mettagrid.mapgen.utils.ascii_grid import DEFAULT_CHAR_TO_NAME
from mettagrid.mettagrid_c import PackedCoordinate
from mettagrid.simulator import Simulation

NUM_OBS_TOKENS = 200


def _positions_with_char(sim: Simulation, ch: str, visible_only: bool = True) -> set[int]:
    """Compute packed coordinates for tiles matching the ASCII char.
    If visible_only, restrict to current observation FoV (tokens with non-empty
    location in the first agent's observation).
    """
    locs: set[int] = set()
    # Optionally gather visible coordinates from current observation
    visible: set[int] | None = None
    if visible_only:
        obs = sim._c_sim.observations()
        agent0 = obs[0]
        visible = {int(t[0]) for t in agent0 if int(t[0]) != 0xFF}
    m = sim.config.game.map_builder.map_data
    for r, row in enumerate(m):
        for c, ch2 in enumerate(row):
            if ch2 == ch:
                packed = PackedCoordinate.pack(c, r)
                if visible is None or packed in visible:
                    locs.add(packed)
    return locs


@pytest.fixture
def sim_with_tags() -> Simulation:
    """Create an environment with objects that have tags."""
    cfg = MettaGridConfig(
        game=GameConfig(
            num_agents=2,
            obs=ObsConfig(width=7, height=7, num_tokens=NUM_OBS_TOKENS),
            max_steps=1000,
            actions=ActionsConfig(noop=NoopActionConfig(), move=MoveActionConfig()),
            objects={"wall": WallConfig(tags=[Tag("solid"), Tag("blocking")])},
            resource_names=[],
            map_builder=AsciiMapBuilder.Config(
                map_data=[
                    ["#", "#", "#", "#", "#", "#", "#"],
                    ["#", "@", ".", ".", ".", ".", "#"],
                    ["#", ".", ".", ".", ".", ".", "#"],
                    ["#", ".", ".", ".", ".", ".", "#"],
                    ["#", "@", ".", ".", ".", ".", "#"],
                    ["#", "#", "#", "#", "#", "#", "#"],
                ],
                char_to_map_name=DEFAULT_CHAR_TO_NAME,
            ),
        )
    )

    return Simulation(cfg)


@pytest.fixture
def sim_with_duplicate_tags() -> Simulation:
    """Create an environment where multiple objects share tags."""
    cfg = MettaGridConfig(
        game=GameConfig(
            num_agents=1,
            obs=ObsConfig(width=5, height=5, num_tokens=NUM_OBS_TOKENS),
            max_steps=1000,
            actions=ActionsConfig(noop=NoopActionConfig(), move=MoveActionConfig()),
            agents=[
                AgentConfig(tags=[Tag("mobile"), Tag("shared_tag")]),
            ],
            objects={"wall": WallConfig(tags=[Tag("solid"), Tag("shared_tag")])},
            resource_names=[],
            map_builder=AsciiMapBuilder.Config(
                map_data=[
                    ["#", "#", "#", "#", "#"],
                    ["#", "@", ".", ".", "#"],
                    ["#", ".", ".", ".", "#"],
                    ["#", ".", ".", ".", "#"],
                    ["#", "#", "#", "#", "#"],
                ],
                char_to_map_name=DEFAULT_CHAR_TO_NAME,
            ),
        )
    )

    return Simulation(cfg)


class TestTags:
    """Test tag system functionality."""

    def test_tags_in_config(self, sim_with_tags):
        """Test that tags are properly configured in the game config."""
        sim = sim_with_tags
        obs = sim._c_sim.observations()

        # Verify environment creates successfully with tags
        assert obs is not None
        assert len(obs) == 2  # Two agents

        # Check that observation has the expected shape
        assert obs.shape[0] == 2  # Two agents
        assert obs.shape[2] == 3  # Each token is [location, feature, value]

        # Look for walls and their tags in agent 0's observation
        agent0_obs = obs[0]

        # Find walls based on map char '#'
        wall_locations = _positions_with_char(sim, "#")

        # Should find walls in the observation
        assert len(wall_locations) > 0, "Should find walls in observation"

        # Get tag feature ID from environment
        tag_feature_id = sim.config.game.id_map().feature_id("tag")

        # Check for tag features in observation (not restricted to location)
        tag_features = [token[2] for token in agent0_obs if token[1] == tag_feature_id]

        # Walls should have tag features
        assert len(tag_features) > 0, "Walls should have tag features"

    def test_tags_in_observations(self, sim_with_tags):
        """Test that tags appear in observations with correct IDs."""
        sim = sim_with_tags
        obs = sim._c_sim.observations()
        agent0_obs = obs[0]

        # Wall has tags ["solid", "blocking"] which should be sorted alphabetically
        # and assigned IDs starting from 0
        # Sorted: ["blocking", "solid"]
        expected_tag_ids = [0, 1]  # 0, 1

        # Get tag feature ID from environment
        tag_feature_id = sim.config.game.id_map().feature_id("tag")

        # Find tag features in observation
        found_tags = {token[2] for token in agent0_obs if token[1] == tag_feature_id}

        # Should find both tag IDs
        assert len(found_tags) >= 2, f"Should find at least 2 tag IDs, found {found_tags}"
        # Both expected tag IDs should be present
        for tag_id in expected_tag_ids:
            assert tag_id in found_tags, f"Tag ID {tag_id} should be in observations"

    def test_empty_tags(self):
        """Objects with no explicit tags get a default kind tag (e.g., 'wall')."""
        cfg = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=3, height=3, num_tokens=NUM_OBS_TOKENS),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                objects={
                    "wall": WallConfig(tags=[]),
                },
                resource_names=[],
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        ["#", "#", "#"],
                        ["#", "@", "#"],
                        ["#", "#", "#"],
                    ],
                    char_to_map_name=DEFAULT_CHAR_TO_NAME,
                ),
            )
        )

        env = Simulation(cfg)
        obs = env._c_sim.observations()

        # Environment should work fine with objects that have no tags
        assert obs is not None

        agent_obs = obs[0]

        # Get tag feature ID from environment
        tag_feature_id = env.config.game.id_map().feature_id("tag")

        # Find wall locations from map data
        wall_locations = _positions_with_char(env, "#")

        # Expect default kind tag present on walls
        wall_tag_tokens = [t for t in agent_obs if t[0] in wall_locations and t[1] == tag_feature_id]
        assert len(wall_tag_tokens) > 0, "Walls should have default 'wall' tag tokens"

    def test_duplicate_tags_across_objects(self, sim_with_duplicate_tags):
        """Test that multiple objects can share the same tags."""
        sim = sim_with_duplicate_tags
        obs = sim._c_sim.observations()
        assert obs is not None

        agent_obs = obs[0]

        # Both agent and wall have "shared_tag"
        # Agent has ["mobile", "shared_tag"]
        # Wall has ["solid", "shared_tag"]
        # Default agent has ["agent"]
        # Sorted all unique tags: ["agent", "mobile", "shared_tag", "solid"]
        # Get the actual shared_tag_id from id_map
        id_map = sim.config.game.id_map()
        tag_names = id_map.tag_names()
        tag_name_to_id = {name: idx for idx, name in enumerate(tag_names)}
        shared_tag_id = tag_name_to_id["shared_tag"]

        # Get tag feature ID from environment
        tag_feature_id = id_map.feature_id("tag")

        # Find wall and agent locations
        wall_locations = _positions_with_char(sim, "#")
        agent_locations = _positions_with_char(sim, "@")

        # Find the shared tag in both agent and wall observations
        found_shared_in_wall = False
        found_shared_in_agent = False

        for token in agent_obs:
            if token[1] == tag_feature_id and token[2] == shared_tag_id:
                if token[0] in wall_locations:
                    found_shared_in_wall = True
                if token[0] in agent_locations:
                    found_shared_in_agent = True

        # The shared tag should appear in at least one type of object
        assert found_shared_in_wall or found_shared_in_agent, "Shared tag should be found in observations"

    def test_many_tags_on_single_object(self):
        """Test that an object can have many tags."""
        tags = [Tag(f"tag{i:02d}") for i in range(1, 11)]  # tag01 through tag10

        cfg = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=3, height=3, num_tokens=NUM_OBS_TOKENS),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                objects={"wall": WallConfig(tags=tags)},
                resource_names=[],
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        ["#", "#", "#"],
                        ["#", "@", "#"],
                        ["#", "#", "#"],
                    ],
                    char_to_map_name=DEFAULT_CHAR_TO_NAME,
                ),
            )
        )

        env = Simulation(cfg)
        obs = env._c_sim.observations()

        # Should handle many tags without issues
        assert obs is not None

        agent_obs = obs[0]

        # Get tag feature ID from environment
        tag_feature_id = env.config.game.id_map().feature_id("tag")

        # Find wall locations from map data
        wall_locations = _positions_with_char(env, "#")

        # Count unique tag IDs found on walls
        tag_ids_found = set()
        for token in agent_obs:
            if token[0] in wall_locations and token[1] == tag_feature_id:
                tag_ids_found.add(token[2])  # token[2] contains the tag ID

        # Should find all 10 explicit tags + type:wall (auto-generated) = 11 total
        assert len(tag_ids_found) == 11, f"Should find all 11 tags, found {len(tag_ids_found)}"

    def test_tag_id_mapping(self):
        """Test that tag names are consistently mapped to IDs."""
        # Create two environments with same tags in different order
        cfg1 = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=3, height=3, num_tokens=200),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                objects={"wall": WallConfig(tags=[Tag("alpha"), Tag("beta")])},
                resource_names=[],
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        [".", ".", "."],
                        [".", "@", "."],
                        [".", ".", "#"],  # Wall in bottom-right
                    ],
                    char_to_map_name=DEFAULT_CHAR_TO_NAME,
                ),
            )
        )

        cfg2 = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(width=3, height=3, num_tokens=200),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                objects={
                    "wall": WallConfig(
                        tags=[Tag("beta"), Tag("alpha")],  # Same tags, different order
                    )
                },
                resource_names=[],
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        [".", ".", "."],
                        [".", "@", "."],
                        [".", ".", "#"],  # Wall in bottom-right
                    ],
                    char_to_map_name=DEFAULT_CHAR_TO_NAME,
                ),
            )
        )

        # Both configs should work and map tags consistently
        env1 = Simulation(cfg1)
        env2 = Simulation(cfg2)

        obs1 = env1._c_sim.observations()
        obs2 = env2._c_sim.observations()

        assert obs1 is not None
        assert obs2 is not None

        # Get tag feature ID from environment
        tag_feature_id = env1.config.game.id_map().feature_id("tag")
        tag_names = env1.config.game.id_map().tag_names()
        alpha_tag_value = tag_names.index("alpha")
        beta_tag_value = tag_names.index("beta")
        type_wall_tag_value = tag_names.index(typeTag("wall"))

        # Extract tag IDs from both environments
        def get_wall_tag_ids(sim, obs):
            wall_locations = _positions_with_char(sim, "#")
            tag_ids = set()
            for token in obs:
                if token[0] in wall_locations and token[1] == tag_feature_id:
                    tag_ids.add(token[2])
            return tag_ids

        tags1 = get_wall_tag_ids(env1, obs1[0])
        tags2 = get_wall_tag_ids(env2, obs2[0])

        # Both should have the same tag IDs (sorted mapping)
        assert tags1 == tags2, f"Tag IDs should be consistent: {tags1} vs {tags2}"
        # Should have exactly 3 tag IDs (alpha, beta, type:wall auto-generated)
        assert len(tags1) == 3, f"Should have 3 tag IDs, got {len(tags1)}"
        # Verify all expected tags are present
        assert tags1 == {alpha_tag_value, beta_tag_value, type_wall_tag_value}, (
            f"Expected tag IDs {{alpha, beta, type:wall}}, got {tags1}"
        )

    def test_agent_with_tags(self):
        """Test that agents can have tags."""
        cfg = MettaGridConfig(
            game=GameConfig(
                num_agents=2,
                obs=ObsConfig(width=3, height=3, num_tokens=200),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig()),
                agents=[
                    AgentConfig(team_id=0, tags=[Tag("player"), Tag("team_red")]),
                    AgentConfig(team_id=1, tags=[Tag("player"), Tag("team_blue")]),
                ],
                resource_names=[],
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        [".", "@", "."],
                        [".", ".", "."],
                        [".", "@", "."],
                    ],
                    char_to_map_name=DEFAULT_CHAR_TO_NAME,
                ),
            )
        )

        env = Simulation(cfg)
        obs = env._c_sim.observations()

        # Get tag feature ID from environment
        tag_feature_id = env.config.game.id_map().feature_id("tag")

        assert obs is not None
        assert len(obs) == 2  # Two agents

        # Check each agent's observation for agent tags
        for agent_idx in range(2):
            agent_obs = obs[agent_idx]
            # Find tag IDs in observation
            agent_tag_ids = {token[2] for token in agent_obs if token[1] == tag_feature_id}
            # Each agent should have at least 2 tags
            assert len(agent_tag_ids) >= 2, f"Agent {agent_idx} should have at least 2 tags, found {len(agent_tag_ids)}"


def test_tag_id_bounds():
    """Test that tag IDs start at 0 and validate bounds."""
    # Create a config with a few tags
    game_config = GameConfig()
    game_config.agents = [
        AgentConfig(team_id=0, tags=[Tag("alpha"), Tag("beta"), Tag("gamma")]),
        AgentConfig(team_id=1, tags=[Tag("delta"), Tag("epsilon")]),
    ]

    # Convert and verify tag IDs start at 0
    cpp_config = convert_to_cpp_game_config(game_config)

    # Tag IDs from explicit agents: alpha, beta, gamma, delta, epsilon + type:agent (auto-generated)
    tag_id_map = cpp_config.tag_id_map
    assert len(tag_id_map) == 6  # 5 explicit tags + type:agent (auto-generated from agent name)

    # Check that tag IDs start at 0
    min_tag_id = min(tag_id_map.keys())
    assert min_tag_id == 0, f"Tag IDs should start at 0, but minimum is {min_tag_id}"

    # Check that tag IDs are sequential
    sorted_ids = sorted(tag_id_map.keys())
    expected_ids = list(range(len(tag_id_map)))
    assert sorted_ids == expected_ids, f"Tag IDs should be sequential from 0, got {sorted_ids}"


def test_too_many_tags_error():
    """Test that having more than 256 tags raises an error."""
    # Create config with 257 unique tags (exceeds uint8 max)
    game_config = GameConfig()

    # Create agents with many unique tags
    tags_per_agent = 50
    num_agents = 6  # 6 * 50 = 300 tags > 256

    game_config.agents = []
    for i in range(num_agents):
        tags = [Tag(f"tag_{i}_{j}") for j in range(tags_per_agent)]
        game_config.agents.append(AgentConfig(team_id=i, tags=tags))

    # Should raise ValueError about too many tags
    with pytest.raises(ValueError) as excinfo:
        convert_to_cpp_game_config(game_config)

    assert "Too many unique tags" in str(excinfo.value)
    assert "256" in str(excinfo.value)


def test_team_tag_consistency_enforced():
    """Test that all agents in a team must have identical tags."""
    game_config = GameConfig()

    # Create agents in same team with different tags
    game_config.agents = [
        AgentConfig(team_id=0, tags=[Tag("alpha"), Tag("beta")]),
        AgentConfig(team_id=0, tags=[Tag("alpha"), Tag("gamma")]),  # Different tags, same team
        AgentConfig(team_id=1, tags=[Tag("delta")]),
    ]

    # Should raise ValueError about inconsistent tags in team
    with pytest.raises(ValueError) as excinfo:
        convert_to_cpp_game_config(game_config)

    assert "All agents in team" in str(excinfo.value)
    assert "must have identical tags" in str(excinfo.value)


def test_team_tag_consistency_success():
    """Test that agents in same team with identical tags work correctly."""
    game_config = GameConfig()

    # Create agents in same team with identical tags
    game_config.agents = [
        AgentConfig(team_id=0, tags=[Tag("alpha"), Tag("beta")]),
        AgentConfig(team_id=0, tags=[Tag("alpha"), Tag("beta")]),  # Same tags, same team - OK
        AgentConfig(team_id=1, tags=[Tag("gamma"), Tag("delta")]),
        AgentConfig(team_id=1, tags=[Tag("gamma"), Tag("delta")]),  # Same tags, same team - OK
    ]

    # Should succeed
    cpp_config = convert_to_cpp_game_config(game_config)

    # Verify tag mapping is correct - tags from explicit agents list + type:agent (auto-generated)
    tag_id_map = cpp_config.tag_id_map
    assert len(tag_id_map) == 5  # alpha, beta, delta, gamma + type:agent (sorted)

    # Verify tags are assigned correctly (sorted alphabetically)
    assert tag_id_map[0] == "alpha"
    assert tag_id_map[1] == "beta"
    assert tag_id_map[2] == "delta"
    assert tag_id_map[3] == "gamma"
    assert tag_id_map[4] == typeTag("agent")


def test_empty_tags_allowed():
    """Test that agents with no tags work correctly."""
    game_config = GameConfig()

    # Create agents with no tags - they will get default type:agent tag from validator
    game_config.agents = [
        AgentConfig(team_id=0, tags=[]),
        AgentConfig(team_id=1, tags=[]),
    ]

    # Should succeed
    cpp_config = convert_to_cpp_game_config(game_config)

    # Verify type:agent tag is in mapping (from validator default + C++ auto-generated, deduplicated)
    tag_id_map = cpp_config.tag_id_map
    assert len(tag_id_map) == 1  # Only type:agent (deduped)
    assert tag_id_map[0] == typeTag("agent")


def test_default_agent_tags_preserved():
    """Test that default agent tags are preserved when agents list is empty."""
    # This test verifies the fix for the issue where default-agent tags were dropped
    # when agents list was empty but game_config.agent.tags was set

    cfg = MettaGridConfig(
        game=GameConfig(
            num_agents=2,  # Will create 2 default agents
            max_steps=100,
            actions=ActionsConfig(noop=NoopActionConfig()),
            agent=AgentConfig(
                tags=[Tag("default_tag1"), Tag("default_tag2")]  # Tags for default agents
            ),
            agents=[],  # Empty agents list - will use defaults from agent field
            resource_names=[],
            map_builder=AsciiMapBuilder.Config(
                map_data=[
                    [".", "@", "."],
                    [".", ".", "."],
                    [".", "@", "."],
                ],
                char_to_map_name=DEFAULT_CHAR_TO_NAME,
            ),
        )
    )

    # Create environment - this will trigger convert_to_cpp_game_config
    env = Simulation(cfg)
    obs = env._c_sim.observations()

    assert obs is not None
    assert len(obs) == 2  # Two default agents

    # Get tag feature ID from environment
    tag_feature_id = env.config.game.id_map().feature_id("tag")

    # Check both agents have the default tags
    for agent_idx in range(2):
        agent_obs = obs[agent_idx]

        # Find tag IDs in observation
        agent_tag_ids = {token[2] for token in agent_obs if token[1] == tag_feature_id}

        # Each default agent should have 3 tags (default_tag1, default_tag2, type:agent)
        assert len(agent_tag_ids) == 3, f"Default agent {agent_idx} should have 3 tags, found {len(agent_tag_ids)}"
        # Tag IDs should be 0, 1, 2 (alphabetically sorted: default_tag1=0, default_tag2=1, type:agent=2)
        assert agent_tag_ids == {0, 1, 2}, (
            f"Default agent {agent_idx} should have tag IDs {{0, 1, 2}}, got {agent_tag_ids}"
        )


def test_default_agent_tags_in_cpp_config():
    """Test that default agent tags are included in the cpp config tag mapping."""
    game_config = GameConfig()

    # Set default agent tags but leave agents list empty
    game_config.agent = AgentConfig(tags=[Tag("hero"), Tag("player")])
    game_config.agents = []  # Empty - will create default agents
    game_config.num_agents = 3  # Will create 3 default agents

    # Convert to cpp config
    cpp_config = convert_to_cpp_game_config(game_config)

    # Verify tag mapping includes the default agent tags
    tag_id_map = cpp_config.tag_id_map
    assert len(tag_id_map) == 3, f"Should have 3 tags in mapping, got {len(tag_id_map)}"

    # Tags should be sorted alphabetically: hero=0, player=1, type:agent=2
    assert tag_id_map[0] == "hero", f"Tag ID 0 should be 'hero', got {tag_id_map[0]}"
    assert tag_id_map[1] == "player", f"Tag ID 1 should be 'player', got {tag_id_map[1]}"
    assert tag_id_map[2] == typeTag("agent"), f"Tag ID 2 should be 'type:agent', got {tag_id_map[2]}"


def test_tag_mapping_in_id_map():
    """Test that tag mapping is exposed through id_map"""
    cfg = MettaGridConfig(
        game=GameConfig(
            num_agents=1,
            obs=ObsConfig(width=3, height=3, num_tokens=NUM_OBS_TOKENS),
            max_steps=100,
            actions=ActionsConfig(noop=NoopActionConfig()),
            objects={
                "wall": WallConfig(tags=[Tag("solid"), Tag("blocking")]),
            },
            # Note: game_config.agent is a template for default agents when agents list is empty.
            # When agents list is explicitly specified (as here), only tags from the agents list are used.
            agents=[
                AgentConfig(tags=[Tag("player"), Tag("mobile")]),
            ],
            resource_names=["wood", "coal"],
            map_builder=AsciiMapBuilder.Config(
                map_data=[
                    ["#", "#", "#"],
                    ["#", "@", "#"],
                    ["#", "#", "#"],
                ],
                char_to_map_name=DEFAULT_CHAR_TO_NAME,
            ),
        )
    )

    sim = Simulation(cfg)
    id_map = sim.config.game.id_map()

    # Check that tag feature exists
    tag_feature_id = id_map.feature_id("tag")
    assert tag_feature_id is not None, "tag feature should exist in id_map"

    # Check tag mapping contents
    tag_values = id_map.tag_names()
    assert isinstance(tag_values, list), "tag values should be a list of tag names"

    # Tags are from objects and agents + auto-generated type tags (sorted alphabetically)
    expected_tags = sorted(
        [
            "blocking",
            "mobile",
            "player",
            "solid",
            typeTag("agent"),
            typeTag("wall"),
        ]
    )
    assert len(tag_values) == len(expected_tags), f"Should have {len(expected_tags)} tags, got {len(tag_values)}"

    # Verify tags are sorted alphabetically with correct IDs (indices)
    for i, expected_tag in enumerate(expected_tags):
        assert i < len(tag_values), f"Tag ID {i} should be in mapping"
        assert tag_values[i] == expected_tag, f"Tag ID {i} should be '{expected_tag}', got '{tag_values[i]}'"


def test_tag_mapping_empty_tags():
    """Tag mapping includes default kind tags when objects have no explicit tags."""
    cfg = MettaGridConfig(
        game=GameConfig(
            num_agents=1,
            obs=ObsConfig(width=3, height=3, num_tokens=NUM_OBS_TOKENS),
            max_steps=100,
            actions=ActionsConfig(noop=NoopActionConfig()),
            objects={
                "wall": WallConfig(tags=[]),
            },
            agents=[
                AgentConfig(tags=[]),  # No agent tags
            ],
            resource_names=[],
            map_builder=AsciiMapBuilder.Config(
                map_data=[
                    ["#", "#", "#"],
                    ["#", "@", "#"],
                    ["#", "#", "#"],
                ],
                char_to_map_name=DEFAULT_CHAR_TO_NAME,
            ),
        )
    )

    env = Simulation(cfg)
    id_map = env.config.game.id_map()

    # Check that tag feature exists
    tag_feature_id = id_map.feature_id("tag")
    assert tag_feature_id is not None

    # Now expect mapping to include the default 'type:wall' tag (from validator)
    tag_values = id_map.tag_names()
    assert isinstance(tag_values, list)
    assert typeTag("wall") in tag_values, f"Expected default 'type:wall' tag. Got {tag_values}"
