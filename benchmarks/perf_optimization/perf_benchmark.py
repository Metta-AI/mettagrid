#!/usr/bin/env -S uv run python

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List

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
from mettagrid.envs.mettagrid_puffer_env import MettaGridPufferEnv
from mettagrid.map_builder.random_map import RandomMapBuilder
from mettagrid.simulator import Simulator


def create_env(num_agents: int = 20, map_size: int = 40, density: float = 0.04, seed: int = 42):
    # Calculate number of wall objects based on density
    num_walls = int(map_size * map_size * density)

    cfg = MettaGridConfig(
        game=GameConfig(
            num_agents=num_agents,
            max_steps=0,
            obs=ObsConfig(width=11, height=11, num_tokens=200),
            actions=ActionsConfig(
                noop=NoopActionConfig(enabled=True),
                move=MoveActionConfig(
                    enabled=True,
                    allowed_directions=[
                        "north",
                        "south",
                        "east",
                        "west",
                        "northeast",
                        "northwest",
                        "southeast",
                        "southwest",
                    ],
                ),
            ),
            objects={
                "wall": WallConfig(render_symbol="X"),
            },
            map_builder=RandomMapBuilder.Config(
                width=map_size,
                height=map_size,
                agents=num_agents,
                objects={"wall": num_walls},
                border_width=1,
                border_object="wall",
                seed=seed,  # Deterministic map
            ),
        )
    )

    simulator = Simulator()
    env = MettaGridPufferEnv(simulator, cfg)
    env.reset()
    return env


def pre_generate_actions(num_agents: int, num_actions: int, total_steps: int, seed: int = 42) -> np.ndarray:
    rng = np.random.RandomState(seed)
    return rng.randint(0, num_actions, size=(total_steps, num_agents))


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


def run_benchmark_round(
    env, actions: np.ndarray, start_idx: int, num_steps: int, profile: bool = False
) -> tuple[float, float, dict | None]:
    """Run a benchmark round, return (total_time, obs_time_sum, phase_totals_or_none)."""
    start = time.perf_counter()
    obs_time_sum = 0.0

    # Get direct access to C++ simulation for timing access
    c_sim = env.current_simulation._c_sim

    phase_totals = {f"{phase}_ns": 0.0 for phase in STEP_TIMING_PHASES} if profile else None
    if profile:
        phase_totals["total_ns"] = 0.0

    for i in range(start_idx, start_idx + num_steps):
        env.step(actions[i])
        if profile:
            obs_time_sum += c_sim.last_obs_time_ns
            timing = c_sim.step_timing
            for key in phase_totals:
                phase_totals[key] += getattr(timing, key)

    total_time = time.perf_counter() - start
    return total_time, obs_time_sum, phase_totals


def calculate_statistics(times: List[float], num_steps: int, num_agents: int) -> dict:
    times_arr = np.array(times)

    # Basic statistics
    mean_time = float(np.mean(times_arr))
    std_time = float(np.std(times_arr))
    min_time = float(np.min(times_arr))
    max_time = float(np.max(times_arr))

    # Performance metrics
    env_sps_mean = num_steps / mean_time
    env_sps_std = env_sps_mean * (std_time / mean_time) if mean_time > 0 else 0
    agent_sps_mean = env_sps_mean * num_agents
    agent_sps_std = env_sps_std * num_agents

    # Percentiles
    p50 = float(np.percentile(times_arr, 50))
    p95 = float(np.percentile(times_arr, 95))
    p99 = float(np.percentile(times_arr, 99))

    return {
        "mean_time": mean_time,
        "std_time": std_time,
        "min_time": min_time,
        "max_time": max_time,
        "p50_time": p50,
        "p95_time": p95,
        "p99_time": p99,
        "env_sps_mean": env_sps_mean,
        "env_sps_std": env_sps_std,
        "agent_sps_mean": agent_sps_mean,
        "agent_sps_std": agent_sps_std,
        "cv": std_time / mean_time if mean_time > 0 else 0,  # Coefficient of variation
    }


def run_performance(env, iterations: int, rounds: int, warmup: int, profile: bool = False) -> dict:
    num_agents = env.num_agents
    num_actions = env.single_action_space.n

    total_steps = warmup + (iterations * rounds)
    print(f"Pre-generating {total_steps:,} action sets...")
    actions = pre_generate_actions(num_agents, num_actions, total_steps)

    print(f"Running {warmup:,} warm-up steps...")
    warmup_start = time.perf_counter()
    for i in range(warmup):
        env.step(actions[i])
    warmup_time = time.perf_counter() - warmup_start

    print(f"Running {rounds} rounds of {iterations:,} steps each...")

    round_times = []
    obs_times = []  # Observations computation times per round
    all_phase_totals = []  # Per-round phase timing accumulations
    action_idx = warmup

    for round_num in range(rounds):
        round_time, obs_time_ns, phase_totals = run_benchmark_round(
            env, actions, action_idx, iterations, profile=profile
        )
        round_times.append(round_time)
        obs_times.append(obs_time_ns / 1e9)  # Convert ns to seconds
        if phase_totals is not None:
            all_phase_totals.append(phase_totals)
        action_idx += iterations

        if (round_num + 1) % 5 == 0:
            print(f"  Completed round {round_num + 1}/{rounds}")

    stats = calculate_statistics(round_times, iterations, num_agents)

    # Add observations-specific metrics (only meaningful when profiling is enabled)
    if profile:
        obs_times_arr = np.array(obs_times)
        stats["obs_time_mean"] = float(np.mean(obs_times_arr))
        stats["obs_time_std"] = float(np.std(obs_times_arr))
        stats["obs_pct_of_step"] = (stats["obs_time_mean"] / stats["mean_time"]) * 100 if stats["mean_time"] > 0 else 0

    print("\nConfiguration:")
    print(f"  Agents: {num_agents}")
    print(f"  Iterations: {iterations:,} per round")
    print(f"  Rounds: {rounds} ({stats['mean_time']:.2f}s/round)")
    print(f"  Warm-up: {warmup:,} steps ({warmup_time:.2f}s)")

    print("\nPerformance Metrics:")
    print(f"  Env SPS: {stats['env_sps_mean']:,.0f} +/- {stats['env_sps_std']:,.0f}")
    print(f"  Agent SPS: {stats['agent_sps_mean']:,.0f} +/- {stats['agent_sps_std']:,.0f}")

    if profile:
        print("\nObservations Timing:")
        print(f"  Obs time: {stats['obs_time_mean'] * 1000:.2f}ms +/- {stats['obs_time_std'] * 1000:.2f}ms per round")
        print(f"  Obs % of step: {stats['obs_pct_of_step']:.1f}%")

    if stats["cv"] < 0.05:
        stability = "Excellent (CV < 5%)"
    elif stats["cv"] < 0.10:
        stability = "Good (CV < 10%)"
    elif stats["cv"] < 0.20:
        stability = "Fair (CV < 20%)"
    else:
        stability = "Poor (CV >= 20%) - results may be unreliable"
    print(f"\nStability: {stability}")

    # Print per-phase step timing breakdown if profiling was enabled
    if all_phase_totals:
        total_steps = iterations * rounds
        # Average across all rounds
        avg_phases = {}
        for key in all_phase_totals[0]:
            avg_phases[key] = sum(pt[key] for pt in all_phase_totals) / total_steps

        mean_total = avg_phases["total_ns"]
        print(f"\nStep Timing Breakdown ({num_agents} agents, {total_steps:,} steps):")
        print(f"  {'Phase':<20} {'Mean (us)':>10} {'% of step':>10}")
        print(f"  {'-' * 42}")
        for phase in STEP_TIMING_PHASES:
            phase_ns = avg_phases[f"{phase}_ns"]
            pct = (phase_ns / mean_total * 100) if mean_total > 0 else 0
            print(f"  {phase:<20} {phase_ns / 1000:>10.2f} {pct:>9.1f}%")
        print(f"  {'-' * 42}")
        print(f"  {'total':<20} {mean_total / 1000:>10.2f} {'100.0%':>10}")

        # Store in stats for JSON output
        stats["step_timing"] = {phase: avg_phases[f"{phase}_ns"] / 1000 for phase in STEP_TIMING_PHASES}
        stats["step_timing"]["total"] = mean_total / 1000

    return stats


def save_results(stats: dict, args, output_path: str) -> None:
    """Save benchmark results to a JSON file."""
    result = {
        "timestamp": datetime.now().isoformat(),
        "phase": args.phase,
        "config": {
            "agents": args.agents,
            "map_size": args.map_size,
            "density": args.density,
            "iterations": args.iterations,
            "rounds": args.rounds,
            "warmup": args.warmup,
            "seed": args.seed,
        },
        "metrics": stats,
    }
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nResults saved to: {output_path}")


def compare_results(baseline_path: str, current: dict, current_phase: str) -> dict:
    """Compare current results against a baseline. Returns comparison dict."""
    with open(baseline_path) as f:
        baseline = json.load(f)

    base_metrics = baseline["metrics"]
    base_phase = baseline.get("phase", "unknown")
    base_sps = base_metrics["agent_sps_mean"]
    curr_sps = current["agent_sps_mean"]
    improvement = ((curr_sps - base_sps) / base_sps) * 100

    comparison = {
        "baseline_phase": base_phase,
        "current_phase": current_phase,
        "baseline_sps": base_sps,
        "current_sps": curr_sps,
        "sps_improvement_pct": improvement,
    }

    if "obs_pct_of_step" in base_metrics and "obs_pct_of_step" in current:
        comparison["baseline_obs_pct"] = base_metrics["obs_pct_of_step"]
        comparison["current_obs_pct"] = current["obs_pct_of_step"]

    if "obs_time_mean" in base_metrics and "obs_time_mean" in current:
        base_obs = base_metrics["obs_time_mean"]
        curr_obs = current["obs_time_mean"]
        comparison["obs_time_improvement_pct"] = ((base_obs - curr_obs) / base_obs) * 100

    return comparison


def print_comparison(comparison: dict) -> None:
    """Print a single comparison."""
    print(f"\n  vs {comparison['baseline_phase']}:")
    print(f"    Baseline Agent SPS: {comparison['baseline_sps']:,.0f}")
    print(f"    Current Agent SPS:  {comparison['current_sps']:,.0f}")
    print(f"    SPS Improvement: {comparison['sps_improvement_pct']:+.1f}%")

    if "obs_time_improvement_pct" in comparison:
        print(f"    Obs time improvement: {comparison['obs_time_improvement_pct']:+.1f}%")
    if "baseline_obs_pct" in comparison:
        print(f"    Obs % of step: {comparison['baseline_obs_pct']:.1f}% -> {comparison['current_obs_pct']:.1f}%")


def compare_multiple(baseline_paths: List[str], current: dict, current_phase: str) -> List[dict]:
    """Compare current results against multiple baselines."""
    comparisons = []
    for baseline_path in baseline_paths:
        if Path(baseline_path).exists():
            comparison = compare_results(baseline_path, current, current_phase)
            comparisons.append(comparison)
        else:
            print(f"Warning: baseline file not found: {baseline_path}")
    return comparisons


def generate_phase_report(results_dir: str, current_stats: dict, current_phase: str) -> None:
    """Generate a summary report showing improvements across all phases."""
    results_path = Path(results_dir)
    if not results_path.exists():
        print(f"Results directory not found: {results_dir}")
        return

    # Find all phase result files
    phase_files = sorted(results_path.glob("phase_*.json"))
    if not phase_files:
        print("No phase result files found.")
        return

    print(f"\n{'=' * 60}")
    print("Phase-by-Phase Performance Summary")
    print(f"{'=' * 60}")

    phases = []
    for pf in phase_files:
        with open(pf) as f:
            data = json.load(f)
            phases.append(
                {
                    "phase": data.get("phase", pf.stem),
                    "agent_sps": data["metrics"]["agent_sps_mean"],
                    "obs_pct": data["metrics"].get("obs_pct_of_step", 0),
                    "obs_time": data["metrics"].get("obs_time_mean", 0),
                    "timestamp": data.get("timestamp", ""),
                }
            )

    # Add current if not already saved
    if current_phase and current_phase not in [p["phase"] for p in phases]:
        phases.append(
            {
                "phase": current_phase,
                "agent_sps": current_stats["agent_sps_mean"],
                "obs_pct": current_stats.get("obs_pct_of_step", 0),
                "obs_time": current_stats.get("obs_time_mean", 0),
                "timestamp": datetime.now().isoformat(),
            }
        )

    # Print table
    print(f"\n{'Phase':<20} {'Agent SPS':>12} {'vs Baseline':>12} {'Obs %':>8}")
    print("-" * 54)

    baseline_sps = phases[0]["agent_sps"] if phases else 0
    for p in phases:
        improvement = ((p["agent_sps"] - baseline_sps) / baseline_sps * 100) if baseline_sps > 0 else 0
        print(f"{p['phase']:<20} {p['agent_sps']:>12,.0f} {improvement:>+11.1f}% {p['obs_pct']:>7.1f}%")

    # Calculate cumulative improvement
    if len(phases) >= 2:
        total_improvement = ((phases[-1]["agent_sps"] - phases[0]["agent_sps"]) / phases[0]["agent_sps"]) * 100
        print("-" * 54)
        print(f"{'Total improvement':<20} {'':<12} {total_improvement:>+11.1f}%")


def main():
    parser = argparse.ArgumentParser(
        description="MettaGrid performance benchmark with phase tracking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run baseline measurement
  python perf_benchmark.py --phase baseline --output results/phase_0_baseline.json

  # Run after Phase 1 optimization
  python perf_benchmark.py --phase phase1 --output results/phase_1.json \\
      --baseline results/phase_0_baseline.json

  # Compare against multiple phases
  python perf_benchmark.py --phase phase2 --output results/phase_2.json \\
      --baseline results/phase_0_baseline.json results/phase_1.json

  # Generate summary report
  python perf_benchmark.py --report results/
        """,
    )
    parser.add_argument("--agents", type=int, default=20, help="Number of agents")
    parser.add_argument("--map-size", type=int, default=40, help="Map width/height")
    parser.add_argument("--density", type=float, default=0.04, help="Grid object density (0.0-1.0)")
    parser.add_argument("--iterations", type=int, default=20000, help="Steps per round")
    parser.add_argument("--rounds", type=int, default=20, help="Number of measurement rounds")
    parser.add_argument("--warmup", type=int, default=150000, help="Warm-up steps")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--output", type=str, help="Save results to JSON file")
    parser.add_argument("--baseline", type=str, nargs="+", help="Compare against baseline JSON file(s)")
    parser.add_argument("--phase", type=str, default="", help="Label for this optimization phase")
    parser.add_argument("--profile", action="store_true", help="Print per-phase step timing breakdown")
    parser.add_argument("--report", type=str, help="Generate summary report from results directory")
    args = parser.parse_args()

    # Report-only mode
    if args.report:
        generate_phase_report(args.report, {}, "")
        return

    if args.profile:
        os.environ["METTAGRID_PROFILING"] = "1"

    print(f"Creating environment: {args.agents} agents on {args.map_size}x{args.map_size} map (density={args.density})")
    if args.phase:
        print(f"Phase: {args.phase}")
    env = create_env(num_agents=args.agents, map_size=args.map_size, density=args.density, seed=args.seed)

    stats = run_performance(
        env, iterations=args.iterations, rounds=args.rounds, warmup=args.warmup, profile=args.profile
    )

    if args.output:
        save_results(stats, args, args.output)

    if args.baseline:
        print(f"\n{'=' * 60}")
        print("Comparisons")
        print(f"{'=' * 60}")
        comparisons = compare_multiple(args.baseline, stats, args.phase or "current")
        for comparison in comparisons:
            print_comparison(comparison)

        # If output file specified, append comparisons
        if args.output:
            with open(args.output) as f:
                result = json.load(f)
            result["comparisons"] = comparisons
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2)

    # Return non-zero exit code if performance is unstable
    if stats["cv"] > 0.20:
        print("\nPerformance measurement unstable!")
        sys.exit(1)


if __name__ == "__main__":
    main()
