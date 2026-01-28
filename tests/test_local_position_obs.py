"""Tests for the local_position global observation feature.

When enabled, agents receive up to 2 tokens per step indicating their
directional offset from spawn: lp:east/west for columns, lp:north/south for rows.
Zero offsets are not emitted.
"""

import pytest

from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    GameConfig,
    GlobalObsConfig,
    MettaGridConfig,
    MoveActionConfig,
    NoopActionConfig,
    ObsConfig,
    WallConfig,
)
from mettagrid.config.tag import Tag
from mettagrid.map_builder.ascii import AsciiMapBuilder
from mettagrid.mapgen.utils.ascii_grid import DEFAULT_CHAR_TO_NAME
from mettagrid.simulator import Location, Simulation
from mettagrid.test_support import ObservationHelper

NUM_OBS_TOKENS = 50


def xy(x: int, y: int) -> Location:
    return Location(row=y, col=x)


def _make_sim(game_map: list[list[str]], num_agents: int = 1) -> Simulation:
    """Create a simulation with local_position enabled."""
    cfg = MettaGridConfig(
        game=GameConfig(
            num_agents=num_agents,
            obs=ObsConfig(
                width=11,
                height=11,
                num_tokens=NUM_OBS_TOKENS,
                global_obs=GlobalObsConfig(
                    local_position=True,
                    episode_completion_pct=False,
                    last_action=False,
                    last_reward=False,
                ),
            ),
            max_steps=100,
            actions=ActionsConfig(noop=NoopActionConfig(), move=MoveActionConfig()),
            objects={"wall": WallConfig(tags=[Tag("wall")])},
            resource_names=[],
            map_builder=AsciiMapBuilder.Config(
                map_data=game_map,
                char_to_map_name=DEFAULT_CHAR_TO_NAME,
            ),
        )
    )
    return Simulation(cfg)


def _get_lp_tokens(sim: Simulation, obs, agent_idx: int = 0) -> dict[str, int]:
    """Extract local position tokens from an agent's observation.

    Returns a dict like {"lp:east": 3, "lp:north": 5} with only the
    non-zero directions present.
    """
    helper = ObservationHelper()
    id_map = sim.config.game.id_map()
    center = xy(sim.config.game.obs.width // 2, sim.config.game.obs.height // 2)

    result = {}
    for name in ("lp:east", "lp:west", "lp:north", "lp:south"):
        fid = id_map.feature_id(name)
        values = helper.find_token_values(obs[agent_idx], location=center, feature_id=fid)
        if len(values) > 0:
            result[name] = int(values[0])
    return result


class TestLocalPositionAtSpawn:
    """Test that no local position tokens are emitted at spawn."""

    def test_no_tokens_at_spawn(self):
        """At spawn, offset is (0,0) so no tokens should be emitted."""
        game_map = [
            ["#", "#", "#", "#", "#"],
            ["#", ".", ".", ".", "#"],
            ["#", ".", "@", ".", "#"],
            ["#", ".", ".", ".", "#"],
            ["#", "#", "#", "#", "#"],
        ]
        sim = _make_sim(game_map)
        # Step once with noop to populate observations
        sim.agent(0).set_action("noop")
        sim.step()
        obs = sim._c_sim.observations()

        tokens = _get_lp_tokens(sim, obs)
        assert tokens == {}, f"Expected no lp tokens at spawn, got {tokens}"


class TestLocalPositionMovement:
    """Test local position tokens after moving in each direction."""

    @pytest.fixture
    def corridor_sim(self) -> Simulation:
        """Agent at center of a large open area with room to move."""
        game_map = [
            ["#", "#", "#", "#", "#", "#", "#", "#", "#"],
            ["#", ".", ".", ".", ".", ".", ".", ".", "#"],
            ["#", ".", ".", ".", ".", ".", ".", ".", "#"],
            ["#", ".", ".", ".", ".", ".", ".", ".", "#"],
            ["#", ".", ".", ".", "@", ".", ".", ".", "#"],
            ["#", ".", ".", ".", ".", ".", ".", ".", "#"],
            ["#", ".", ".", ".", ".", ".", ".", ".", "#"],
            ["#", ".", ".", ".", ".", ".", ".", ".", "#"],
            ["#", "#", "#", "#", "#", "#", "#", "#", "#"],
        ]
        return _make_sim(game_map)

    def test_move_east(self, corridor_sim):
        """Moving east should produce lp:east token."""
        sim = corridor_sim
        sim.agent(0).set_action("move_east")
        sim.step()
        obs = sim._c_sim.observations()

        tokens = _get_lp_tokens(sim, obs)
        assert tokens == {"lp:east": 1}, f"Expected lp:east=1, got {tokens}"

    def test_move_west(self, corridor_sim):
        """Moving west should produce lp:west token."""
        sim = corridor_sim
        sim.agent(0).set_action("move_west")
        sim.step()
        obs = sim._c_sim.observations()

        tokens = _get_lp_tokens(sim, obs)
        assert tokens == {"lp:west": 1}, f"Expected lp:west=1, got {tokens}"

    def test_move_north(self, corridor_sim):
        """Moving north (lower row) should produce lp:north token."""
        sim = corridor_sim
        sim.agent(0).set_action("move_north")
        sim.step()
        obs = sim._c_sim.observations()

        tokens = _get_lp_tokens(sim, obs)
        assert tokens == {"lp:north": 1}, f"Expected lp:north=1, got {tokens}"

    def test_move_south(self, corridor_sim):
        """Moving south (higher row) should produce lp:south token."""
        sim = corridor_sim
        sim.agent(0).set_action("move_south")
        sim.step()
        obs = sim._c_sim.observations()

        tokens = _get_lp_tokens(sim, obs)
        assert tokens == {"lp:south": 1}, f"Expected lp:south=1, got {tokens}"

    def test_move_multiple_steps(self, corridor_sim):
        """Moving multiple steps accumulates offset."""
        sim = corridor_sim
        for _ in range(3):
            sim.agent(0).set_action("move_east")
            sim.step()
        obs = sim._c_sim.observations()

        tokens = _get_lp_tokens(sim, obs)
        assert tokens == {"lp:east": 3}, f"Expected lp:east=3 after 3 east steps, got {tokens}"

    def test_diagonal_offset(self, corridor_sim):
        """Moving east then south should produce both lp:east and lp:south."""
        sim = corridor_sim
        sim.agent(0).set_action("move_east")
        sim.step()
        sim.agent(0).set_action("move_east")
        sim.step()
        sim.agent(0).set_action("move_south")
        sim.step()
        obs = sim._c_sim.observations()

        tokens = _get_lp_tokens(sim, obs)
        assert tokens == {"lp:east": 2, "lp:south": 1}, f"Expected east=2, south=1, got {tokens}"

    def test_return_to_spawn(self, corridor_sim):
        """Moving away then back should result in no tokens."""
        sim = corridor_sim
        sim.agent(0).set_action("move_east")
        sim.step()
        sim.agent(0).set_action("move_west")
        sim.step()
        obs = sim._c_sim.observations()

        tokens = _get_lp_tokens(sim, obs)
        assert tokens == {}, f"Expected no tokens after returning to spawn, got {tokens}"

    def test_cross_spawn_axis(self, corridor_sim):
        """Moving east then further west should switch from lp:east to lp:west."""
        sim = corridor_sim
        # Move 1 east
        sim.agent(0).set_action("move_east")
        sim.step()
        obs = sim._c_sim.observations()
        tokens = _get_lp_tokens(sim, obs)
        assert "lp:east" in tokens

        # Move 2 west (net: 1 west of spawn)
        sim.agent(0).set_action("move_west")
        sim.step()
        sim.agent(0).set_action("move_west")
        sim.step()
        obs = sim._c_sim.observations()

        tokens = _get_lp_tokens(sim, obs)
        assert tokens == {"lp:west": 1}, f"Expected lp:west=1 after crossing axis, got {tokens}"

    def test_only_horizontal_when_vertical_zero(self, corridor_sim):
        """When only horizontal offset is non-zero, only horizontal token emitted."""
        sim = corridor_sim
        sim.agent(0).set_action("move_east")
        sim.step()
        obs = sim._c_sim.observations()

        tokens = _get_lp_tokens(sim, obs)
        assert "lp:north" not in tokens and "lp:south" not in tokens, f"Should have no vertical tokens, got {tokens}"


class TestLocalPositionDisabled:
    """Test that no tokens are emitted when local_position is disabled."""

    def test_disabled_by_default(self):
        """With default config, no lp tokens should exist."""
        game_map = [
            ["#", "#", "#", "#", "#"],
            ["#", ".", ".", ".", "#"],
            ["#", ".", "@", ".", "#"],
            ["#", ".", ".", ".", "#"],
            ["#", "#", "#", "#", "#"],
        ]
        cfg = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                obs=ObsConfig(
                    width=5,
                    height=5,
                    num_tokens=NUM_OBS_TOKENS,
                    global_obs=GlobalObsConfig(local_position=False),
                ),
                max_steps=100,
                actions=ActionsConfig(noop=NoopActionConfig(), move=MoveActionConfig()),
                objects={"wall": WallConfig(tags=[Tag("wall")])},
                resource_names=[],
                map_builder=AsciiMapBuilder.Config(
                    map_data=game_map,
                    char_to_map_name=DEFAULT_CHAR_TO_NAME,
                ),
            )
        )
        sim = Simulation(cfg)

        # Move east and step
        sim.agent(0).set_action("move_east")
        sim.step()
        obs = sim._c_sim.observations()

        # Even though agent moved, no lp tokens should appear
        helper = ObservationHelper()
        id_map = sim.config.game.id_map()
        center = xy(sim.config.game.obs.width // 2, sim.config.game.obs.height // 2)

        for name in ("lp:east", "lp:west", "lp:north", "lp:south"):
            fid = id_map.feature_id(name)
            values = helper.find_token_values(obs[0], location=center, feature_id=fid)
            assert len(values) == 0, f"Expected no {name} token when disabled, got {values}"
