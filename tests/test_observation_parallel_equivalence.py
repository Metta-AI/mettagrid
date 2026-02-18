"""Regression test: multi-threaded obs computation matches single-threaded."""

# ruff: noqa: PLC0415  — imports must be deferred until after env var is set

import numpy as np
import pytest

from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    GameConfig,
    MettaGridConfig,
    MoveActionConfig,
    NoopActionConfig,
    ObsConfig,
)
from mettagrid.map_builder.random_map import RandomMapBuilder
from mettagrid.simulator.simulator import Buffers, Simulation, Simulator


def _run_simulation(monkeypatch: pytest.MonkeyPatch, num_threads: int | str, num_agents: int, steps: int, seed: int):
    """Run a simulation and return per-step observations.

    Note: METTAGRID_OBS_THREADS is read at MettaGrid construction time (C++ side),
    so setting it before creating the Simulation is sufficient.
    num_threads can be an int or "auto".
    """
    monkeypatch.setenv("METTAGRID_OBS_THREADS", str(num_threads))

    num_tokens = 64
    cfg = MettaGridConfig(
        game=GameConfig(
            num_agents=num_agents,
            max_steps=0,
            obs=ObsConfig(width=11, height=11, num_tokens=num_tokens),
            actions=ActionsConfig(noop=NoopActionConfig(enabled=True), move=MoveActionConfig(enabled=True)),
            map_builder=RandomMapBuilder.Config(width=40, height=40, agents=num_agents, seed=0),
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
    all_obs = []
    try:
        sim = Simulation(cfg, seed=seed, simulator=simulator, buffers=buffers)
        rng = np.random.default_rng(seed)
        for _ in range(steps):
            buffers.actions[:] = rng.integers(0, 2, size=(num_agents,), dtype=np.int32)
            sim._c_sim.step()
            all_obs.append(buffers.observations.copy())
    finally:
        simulator.close()

    return all_obs


@pytest.mark.parametrize("num_agents", [8, 20])
def test_parallel_observations_match_serial(monkeypatch: pytest.MonkeyPatch, num_agents: int) -> None:
    pytest.importorskip("mettagrid.mettagrid_c")

    steps = 20
    seed = 42

    serial_obs = _run_simulation(monkeypatch, num_threads=1, num_agents=num_agents, steps=steps, seed=seed)
    parallel_obs = _run_simulation(monkeypatch, num_threads=4, num_agents=num_agents, steps=steps, seed=seed)

    assert len(serial_obs) == len(parallel_obs) == steps
    mismatches = sum(1 for s, p in zip(serial_obs, parallel_obs, strict=True) if not np.array_equal(s, p))
    assert mismatches == 0, f"{mismatches}/{steps} steps had observation mismatches"


def test_auto_thread_count_matches_serial(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify METTAGRID_OBS_THREADS=auto produces identical observations to serial."""
    pytest.importorskip("mettagrid.mettagrid_c")

    steps = 20
    seed = 42
    num_agents = 20

    serial_obs = _run_simulation(monkeypatch, num_threads=1, num_agents=num_agents, steps=steps, seed=seed)
    auto_obs = _run_simulation(monkeypatch, num_threads="auto", num_agents=num_agents, steps=steps, seed=seed)

    assert len(serial_obs) == len(auto_obs) == steps
    mismatches = sum(1 for s, a in zip(serial_obs, auto_obs, strict=True) if not np.array_equal(s, a))
    assert mismatches == 0, f"{mismatches}/{steps} steps had observation mismatches with auto thread count"
