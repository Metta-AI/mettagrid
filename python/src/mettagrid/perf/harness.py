"""Reusable performance benchmarking harness for MettaGrid environments.

This module provides the core step loop, timing, statistics, comparison, and
reporting functions used by benchmark scripts in both mettagrid and cogames.

The harness expects an env with:
- .num_agents
- .single_action_space.n
- .step(actions)
- .current_simulation._c_sim (optional, for profiling)
"""

import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np

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


def pre_generate_actions(num_agents: int, num_actions: int, total_steps: int, seed: int = 42) -> np.ndarray:
    rng = np.random.RandomState(seed)
    return rng.randint(0, num_actions, size=(total_steps, num_agents))


def run_benchmark_round(
    env, actions: np.ndarray, start_idx: int, num_steps: int, profile: bool = False
) -> tuple[float, float, dict | None]:
    """Run a benchmark round, return (total_time, obs_time_sum, phase_totals_or_none)."""
    start = time.perf_counter()
    obs_time_sum = 0.0

    # Get direct access to C++ simulation for timing access
    c_sim = env.current_simulation._c_sim

    phase_totals: dict | None = None
    if profile:
        phase_totals = {f"{phase}_ns": 0.0 for phase in STEP_TIMING_PHASES}
        phase_totals["total_ns"] = 0.0

    for i in range(start_idx, start_idx + num_steps):
        env.step(actions[i])
        if profile and phase_totals is not None:
            obs_time_sum += c_sim.last_obs_time_ns
            timing = c_sim.step_timing
            for key in phase_totals:
                phase_totals[key] += getattr(timing, key)

    total_time = time.perf_counter() - start
    return total_time, obs_time_sum, phase_totals


def calculate_statistics(times: list[float], num_steps: int, num_agents: int) -> dict:
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
        "cv": std_time / mean_time if mean_time > 0 else 0,
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
    obs_times = []
    all_phase_totals = []
    action_idx = warmup

    for round_num in range(rounds):
        round_time, obs_time_ns, phase_totals = run_benchmark_round(
            env, actions, action_idx, iterations, profile=profile
        )
        round_times.append(round_time)
        obs_times.append(obs_time_ns / 1e9)
        if phase_totals is not None:
            all_phase_totals.append(phase_totals)
        action_idx += iterations

        if (round_num + 1) % 5 == 0:
            print(f"  Completed round {round_num + 1}/{rounds}")

    stats = calculate_statistics(round_times, iterations, num_agents)

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

    # Per-phase step timing breakdown
    if all_phase_totals:
        measured_steps = iterations * rounds
        avg_phases = {}
        for key in all_phase_totals[0]:
            avg_phases[key] = sum(pt[key] for pt in all_phase_totals) / measured_steps

        mean_total = avg_phases["total_ns"]
        print(f"\nStep Timing Breakdown ({num_agents} agents, {measured_steps:,} steps):")
        print(f"  {'Phase':<20} {'Mean (us)':>10} {'% of step':>10}")
        print(f"  {'-' * 42}")
        for phase in STEP_TIMING_PHASES:
            phase_ns = avg_phases[f"{phase}_ns"]
            pct = (phase_ns / mean_total * 100) if mean_total > 0 else 0
            print(f"  {phase:<20} {phase_ns / 1000:>10.2f} {pct:>9.1f}%")
        print(f"  {'-' * 42}")
        print(f"  {'total':<20} {mean_total / 1000:>10.2f} {'100.0%':>10}")

        stats["step_timing"] = {phase: avg_phases[f"{phase}_ns"] / 1000 for phase in STEP_TIMING_PHASES}
        stats["step_timing"]["total"] = mean_total / 1000

    # Observations validation stats
    c_sim = env.current_simulation._c_sim
    val_stats = c_sim.obs_validation_stats
    if val_stats.comparison_count > 0:
        mismatches = val_stats.mismatch_count
        comparisons = val_stats.comparison_count
        original_ns = val_stats.original_time_ns
        optimized_ns = val_stats.optimized_time_ns

        status = "PASS" if mismatches == 0 else "FAIL"
        timing_ratio = original_ns / optimized_ns if optimized_ns > 0 else float("inf")

        print("\nObservations Validation:")
        print(f"  Comparisons: {comparisons:,}")
        print(f"  Mismatches: {mismatches:,} — {status}")
        print(f"  Timing ratio: original/optimized = {timing_ratio:.2f}x")

        stats["validation_comparisons"] = comparisons
        stats["validation_mismatches"] = mismatches
        stats["validation_timing_ratio"] = timing_ratio

    return stats


def save_results(stats: dict, config: dict, phase: str, output_path: str) -> None:
    """Save benchmark results to a JSON file.

    Args:
        stats: Metrics dict from run_performance.
        config: Dict of benchmark parameters (agents, map_size, iterations, etc.).
        phase: Label for this optimization phase.
        output_path: Path to write JSON output.
    """
    result = {
        "timestamp": datetime.now().isoformat(),
        "phase": phase,
        "config": config,
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


def compare_multiple(baseline_paths: list[str], current: dict, current_phase: str) -> list[dict]:
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

    print(f"\n{'Phase':<20} {'Agent SPS':>12} {'vs Baseline':>12} {'Obs %':>8}")
    print("-" * 54)

    baseline_sps = phases[0]["agent_sps"] if phases else 0
    for p in phases:
        improvement = ((p["agent_sps"] - baseline_sps) / baseline_sps * 100) if baseline_sps > 0 else 0
        print(f"{p['phase']:<20} {p['agent_sps']:>12,.0f} {improvement:>+11.1f}% {p['obs_pct']:>7.1f}%")

    if len(phases) >= 2:
        total_improvement = ((phases[-1]["agent_sps"] - phases[0]["agent_sps"]) / phases[0]["agent_sps"]) * 100
        print("-" * 54)
        print(f"{'Total improvement':<20} {'':<12} {total_improvement:>+11.1f}%")


def print_scorecard_reminder(
    stats: dict,
    *,
    config_label: str,
    runs_label: str,
    num_rounds: int,
    phase: str = "",
    baseline_paths: list[str] | None = None,
    output_path: str | None = None,
) -> None:
    """Print a scorecard-ready row and reminder to update the perf scorecard."""
    agent_sps = stats["agent_sps_mean"]
    delta = ""
    if baseline_paths:
        first_baseline = Path(baseline_paths[0])
        if first_baseline.exists():
            with open(first_baseline) as f:
                baseline = json.load(f)
            base_sps = baseline["metrics"]["agent_sps_mean"]
            pct = ((agent_sps - base_sps) / base_sps) * 100
            delta = f"{pct:+.0f}% agent SPS"

    print(f"\n{'=' * 60}")
    print("Scorecard row (paste into docs/perf/scorecard.md):")
    print(f"| #???? | {config_label} | {phase or 'main'} | {runs_label} | {num_rounds} | {delta or 'TBD'} | TBD | |")
    if output_path:
        print(f"\nUpdate perf scorecard → /tr.perf-scorecard {output_path}")
    else:
        print("\nUpdate perf scorecard → /tr.perf-scorecard")
