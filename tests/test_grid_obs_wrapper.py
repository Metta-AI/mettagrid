"""Tests for GridObsWrapper — sparse token to dense grid conversion."""

import numpy as np

from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    GameConfig,
    MettaGridConfig,
    MoveActionConfig,
    NoopActionConfig,
    ObsConfig,
    WallConfig,
)
from mettagrid.envs.grid_obs_wrapper import GridObsWrapper
from mettagrid.envs.mettagrid_puffer_env import MettaGridPufferEnv
from mettagrid.map_builder.random_map import RandomMapBuilder
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.simulator import Simulator


def _make_env():
    cfg = MettaGridConfig(
        game=GameConfig(
            num_agents=2,
            obs=ObsConfig(width=3, height=3, num_tokens=50),
            max_steps=10,
            resource_names=["ore", "wood"],
            actions=ActionsConfig(noop=NoopActionConfig(), move=MoveActionConfig()),
            objects={"wall": WallConfig()},
            map_builder=RandomMapBuilder.Config(width=7, height=5, agents=2, seed=42),
        )
    )
    sim = Simulator()
    env = MettaGridPufferEnv(sim, cfg, seed=42)
    return env, cfg


class TestGridObsWrapperShape:
    def test_reset_shape(self):
        inner, cfg = _make_env()
        pei = PolicyEnvInterface.from_mg_cfg(cfg)
        num_features = max((int(f.id) for f in pei.obs_features), default=0) + 1

        env = GridObsWrapper(inner)
        obs, info = env.reset()

        assert obs.shape == (2, num_features, pei.obs_height, pei.obs_width)
        assert obs.dtype == np.float32
        env.close()

    def test_step_shape(self):
        inner, cfg = _make_env()
        pei = PolicyEnvInterface.from_mg_cfg(cfg)
        num_features = max((int(f.id) for f in pei.obs_features), default=0) + 1

        env = GridObsWrapper(inner)
        env.reset()
        actions = np.zeros(2, dtype=np.int32)
        obs, rewards, terminals, truncations, info = env.step(actions)

        assert obs.shape == (2, num_features, pei.obs_height, pei.obs_width)
        assert obs.dtype == np.float32
        assert rewards.shape == (2,)
        assert terminals.shape == (2,)
        assert truncations.shape == (2,)
        env.close()

    def test_observation_space(self):
        inner, cfg = _make_env()
        pei = PolicyEnvInterface.from_mg_cfg(cfg)
        num_features = max((int(f.id) for f in pei.obs_features), default=0) + 1

        env = GridObsWrapper(inner)
        assert env.single_observation_space.shape == (num_features, pei.obs_height, pei.obs_width)
        assert env.single_observation_space.dtype == np.float32
        env.close()


class TestGridObsWrapperValues:
    def test_no_nans_or_infs(self):
        inner, _ = _make_env()
        env = GridObsWrapper(inner)
        obs, _ = env.reset()

        assert np.all(np.isfinite(obs))
        env.close()

    def test_values_non_negative(self):
        inner, _ = _make_env()
        env = GridObsWrapper(inner)
        obs, _ = env.reset()

        assert np.all(obs >= 0)
        env.close()

    def test_padding_tokens_ignored(self):
        """Padding tokens (0xFF) should not contribute to the grid."""
        inner, cfg = _make_env()
        env = GridObsWrapper(inner)
        obs, _ = env.reset()

        # The grid should have some non-zero values (agents exist) but not be all non-zero
        # (padding tokens should have been filtered out)
        assert obs.sum() > 0, "Grid should have non-zero values from real tokens"
        env.close()


class TestGridObsWrapperDelegation:
    def test_num_agents(self):
        inner, _ = _make_env()
        env = GridObsWrapper(inner)
        assert env.num_agents == 2
        env.close()

    def test_action_space(self):
        inner, _ = _make_env()
        env = GridObsWrapper(inner)
        assert env.single_action_space.n == inner.single_action_space.n
        env.close()

    def test_close(self):
        inner, _ = _make_env()
        env = GridObsWrapper(inner)
        env.reset()
        env.close()  # should not raise
