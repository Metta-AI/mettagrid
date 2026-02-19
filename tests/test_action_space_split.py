"""Tests for action-space separation between non-vibe and vibe actions."""

from mettagrid.config.action_config import CHANGE_VIBE_PREFIX, ChangeVibeActionConfig
from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    GameConfig,
    MettaGridConfig,
    MoveActionConfig,
    NoopActionConfig,
    ObsConfig,
    WallConfig,
)
from mettagrid.config.vibes import VIBE_BY_NAME
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.simulator import Simulation
from mettagrid.test_support.map_builders import ObjectNameMapBuilder


def test_policy_env_interface_splits_action_spaces_by_prefix() -> None:
    """PolicyEnvInterface should expose non-vibe/vibe action partitions."""
    map_data = [
        ["wall", "wall", "wall", "wall", "wall"],
        ["wall", "empty", "empty", "empty", "wall"],
        ["wall", "empty", "agent.default", "empty", "wall"],
        ["wall", "empty", "empty", "empty", "wall"],
        ["wall", "wall", "wall", "wall", "wall"],
    ]
    config = MettaGridConfig(
        game=GameConfig(
            num_agents=1,
            obs=ObsConfig(width=5, height=5, num_tokens=80),
            max_steps=10,
            actions=ActionsConfig(
                noop=NoopActionConfig(),
                move=MoveActionConfig(),
                change_vibe=ChangeVibeActionConfig(
                    enabled=True, vibes=[VIBE_BY_NAME["default"], VIBE_BY_NAME["junction"]]
                ),
            ),
            objects={"wall": WallConfig()},
            map_builder=ObjectNameMapBuilder.Config(map_data=map_data),
        )
    )
    sim = Simulation(config)

    # Ensure split fields are available from configuration-derived interface.
    env_info = PolicyEnvInterface.from_mg_cfg(config)
    assert env_info.non_vibe_action_names == sim.non_vibe_action_names
    assert env_info.vibe_action_names == sim.vibe_action_names
    assert env_info.action_space.n == len(sim.non_vibe_action_names)
    assert env_info.vibe_action_space.n == len(sim.vibe_action_names)

    # Fallback split logic still works when new fields are missing.
    fallback = [name for name in env_info.action_names if not name.startswith(CHANGE_VIBE_PREFIX)]
    assert env_info.non_vibe_action_names == fallback


def _agent_object(sim: Simulation, agent_id: int) -> dict:
    for obj in sim.grid_objects().values():
        if obj.get("agent_id") == agent_id:
            return obj
    raise AssertionError(f"Agent {agent_id} object not found")


def test_simulation_processes_vibe_and_non_vibe_actions_in_same_step() -> None:
    """Directly set both action buffers and verify both streams are processed."""
    map_data = [
        ["wall", "wall", "wall", "wall", "wall"],
        ["wall", "empty", "empty", "empty", "wall"],
        ["wall", "empty", "agent.default", "empty", "wall"],
        ["wall", "empty", "empty", "empty", "wall"],
        ["wall", "wall", "wall", "wall", "wall"],
    ]
    config = MettaGridConfig(
        game=GameConfig(
            num_agents=1,
            obs=ObsConfig(width=5, height=5, num_tokens=80),
            max_steps=10,
            actions=ActionsConfig(
                noop=NoopActionConfig(),
                move=MoveActionConfig(),
                change_vibe=ChangeVibeActionConfig(
                    enabled=True, vibes=[VIBE_BY_NAME["default"], VIBE_BY_NAME["junction"]]
                ),
            ),
            objects={"wall": WallConfig()},
            map_builder=ObjectNameMapBuilder.Config(map_data=map_data),
        )
    )
    sim = Simulation(config)

    before = _agent_object(sim, 0)
    before_col = before["c"]

    move_action = sim.non_vibe_action_ids["move_east"]
    vibe_action = sim.vibe_action_ids["change_vibe_junction"]

    sim._c_sim.actions()[0] = move_action
    sim._c_sim.vibe_actions()[0] = vibe_action
    sim.step()

    after = _agent_object(sim, 0)
    assert after["c"] == before_col + 1
    assert after["vibe"] == 1
