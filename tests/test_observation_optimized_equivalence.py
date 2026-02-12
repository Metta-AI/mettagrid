"""Regression tests for optimized observation computation."""

import numpy as np
import pytest


def test_optimized_observations_match_original(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("mettagrid.mettagrid_c")

    # Force shadow-validation mode (primary vs secondary path comparison) in C++.
    monkeypatch.setenv("METTAGRID_OBS_VALIDATION", "1")
    monkeypatch.delenv("METTAGRID_OBS_USE_OPTIMIZED", raising=False)

    from mettagrid.config.mettagrid_config import (  # noqa: PLC0415
        ActionsConfig,
        GameConfig,
        MettaGridConfig,
        MoveActionConfig,
        NoopActionConfig,
        ObsConfig,
    )
    from mettagrid.map_builder.random_map import RandomMapBuilder  # noqa: PLC0415
    from mettagrid.simulator.simulator import Buffers, Simulation, Simulator  # noqa: PLC0415

    num_agents = 4
    num_tokens = 64
    cfg = MettaGridConfig(
        game=GameConfig(
            num_agents=num_agents,
            max_steps=0,
            obs=ObsConfig(width=7, height=7, num_tokens=num_tokens),
            actions=ActionsConfig(noop=NoopActionConfig(enabled=True), move=MoveActionConfig(enabled=True)),
            map_builder=RandomMapBuilder.Config(width=20, height=20, agents=num_agents, seed=0),
        )
    )

    buffers = Buffers(
        observations=np.zeros((num_agents, num_tokens, 3), dtype=np.uint8),
        terminals=np.zeros(num_agents, dtype=np.bool_),
        truncations=np.zeros(num_agents, dtype=np.bool_),
        rewards=np.zeros(num_agents, dtype=np.float32),
        masks=np.ones(num_agents, dtype=np.bool_),
        actions=np.zeros(num_agents, dtype=np.int32),
        teacher_actions=np.zeros(num_agents, dtype=np.int32),
    )

    simulator = Simulator()
    try:
        sim = Simulation(cfg, seed=123, simulator=simulator, buffers=buffers)
        rng = np.random.default_rng(0)
        for _ in range(5):
            buffers.actions[:] = rng.integers(0, 2, size=(num_agents,), dtype=np.int32)
            sim._c_sim.step()

        stats = sim._c_sim.obs_validation_stats
        assert stats.comparison_count > 0
        assert stats.mismatch_count == 0
    finally:
        simulator.close()
