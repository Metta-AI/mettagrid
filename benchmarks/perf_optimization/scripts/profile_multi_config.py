#!/usr/bin/env -S uv run python
"""Profile step timing across Toy, Arena, and CogsGuard configs.

Run on the benchmark branch (monica/obs-perf-benchmark).
Reproduces the multi-config profiling comment on PR #6640.
"""

import os
import time

import numpy as np

from mettagrid.builder import envs
from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    GameConfig,
    MettaGridConfig,
    MoveActionConfig,
    NoopActionConfig,
    ObsConfig,
    WallConfig,
)
from mettagrid.envs.mettagrid_puffer_env import MettaGridPufferEnv
from mettagrid.map_builder.random_map import RandomMapBuilder
from mettagrid.simulator import Simulator

STEP_TIMING_PHASES = [
    "reset",
    "events",
    "actions",
    "on_tick",
    "aoe",
    "collectives",
    "observations",
    "rewards",
    "truncation",
]


def profile_env(label, config, num_steps=15000, warmup=5000):
    simulator = Simulator()
    env = MettaGridPufferEnv(simulator, config)
    env.reset()

    num_agents = env.num_agents
    num_actions = env.single_action_space.n
    rng = np.random.RandomState(42)

    total_steps = warmup + num_steps
    actions = rng.randint(0, num_actions, size=(total_steps, num_agents))

    c_sim = env.current_simulation._c_sim

    # Warmup
    for i in range(warmup):
        env.step(actions[i])

    # Profiled run
    phase_totals = {f"{phase}_ns": 0.0 for phase in STEP_TIMING_PHASES}
    phase_totals["total_ns"] = 0.0

    start = time.perf_counter()
    for i in range(warmup, total_steps):
        env.step(actions[i])
        timing = c_sim.step_timing
        for key in phase_totals:
            phase_totals[key] += getattr(timing, key)
    wall_time = time.perf_counter() - start

    agent_sps = int(num_steps * num_agents / wall_time)

    # Print results
    mean_total = phase_totals["total_ns"] / num_steps
    print(f"\n{'=' * 60}")
    print(f"{label} ({num_agents} agents, {num_actions} actions, {num_steps:,} steps)")
    print(f"{'=' * 60}")
    print(f"  Agent SPS: {agent_sps:,}")
    print(f"  Wall time: {wall_time:.2f}s")
    print(f"\n  {'Phase':<20} {'Mean (us)':>10} {'% of C++':>10} {'% of wall':>10}")
    print(f"  {'-' * 52}")

    wall_per_step_ns = (wall_time / num_steps) * 1e9
    for phase in STEP_TIMING_PHASES:
        phase_ns = phase_totals[f"{phase}_ns"] / num_steps
        pct_cpp = (phase_ns / mean_total * 100) if mean_total > 0 else 0
        pct_wall = (phase_ns / wall_per_step_ns * 100) if wall_per_step_ns > 0 else 0
        if pct_cpp >= 1.0:  # Only show phases >= 1%
            print(f"  {phase:<20} {phase_ns / 1000:>10.2f} {pct_cpp:>9.1f}% {pct_wall:>9.1f}%")
    print(f"  {'-' * 52}")
    print(f"  {'C++ total':<20} {mean_total / 1000:>10.2f}")

    return {
        "label": label,
        "num_agents": num_agents,
        "num_actions": num_actions,
        "agent_sps": agent_sps,
        "phases": {phase: phase_totals[f"{phase}_ns"] / num_steps for phase in STEP_TIMING_PHASES},
        "total_ns": mean_total,
    }


def main():
    os.environ["METTAGRID_PROFILING"] = "1"

    print("Multi-config step timing profiles")
    print("(random actions, current branch, no optimizations active)\n")

    # Toy: default perf_benchmark config (20 agents, move+noop, 40x40, walls only)
    toy_config = MettaGridConfig(
        game=GameConfig(
            num_agents=20,
            max_steps=0,
            obs=ObsConfig(width=11, height=11, num_tokens=200),
            actions=ActionsConfig(
                noop=NoopActionConfig(enabled=True),
                move=MoveActionConfig(
                    enabled=True,
                    allowed_directions=["north", "south", "east", "west"],
                ),
            ),
            objects={"wall": WallConfig(render_symbol="X")},
            map_builder=RandomMapBuilder.Config(
                width=40,
                height=40,
                agents=20,
                objects={"wall": 64},
                border_width=1,
                border_object="wall",
                seed=42,
            ),
        )
    )
    profile_env("Toy", toy_config)

    # Arena: 24 agents, combat=True
    arena_config = envs.make_arena(num_agents=24, combat=True)
    profile_env("Arena (combat=True)", arena_config)

    # CogsGuard: 8 agents, machina_1
    try:
        from recipes.experiment import cogsguard  # noqa: PLC0415
    except ImportError:
        cogsguard = None
    if cogsguard is not None:
        cg_config = cogsguard.make_env(num_agents=8, layout="machina_1")
        profile_env("CogsGuard (machina_1)", cg_config)
    else:
        print("\nSkipping CogsGuard: recipes.experiment.cogsguard not available")


if __name__ == "__main__":
    main()
