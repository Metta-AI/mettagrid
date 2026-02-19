#!/usr/bin/env -S uv run python

import argparse
import json
import os
import sys

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
from mettagrid.perf.harness import (
    compare_multiple,
    generate_phase_report,
    print_comparison,
    run_performance,
    save_results,
)
from mettagrid.simulator import Simulator

PRESET_CONFIGS = {
    "toy": "20 agents, move+noop, 40x40 random map (fast sanity check)",
    "arena": "24 agents, combat, via envs.make_arena (production training config)",
}


def create_env(num_agents: int = 20, map_size: int = 40, density: float = 0.04, seed: int = 42):
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
                seed=seed,
            ),
        )
    )

    simulator = Simulator()
    env = MettaGridPufferEnv(simulator, cfg)
    env.reset()
    return env


def create_env_from_preset(preset: str, seed: int = 42):
    """Create an environment from a named preset config."""
    if preset == "toy":
        return create_env(seed=seed)
    elif preset == "arena":
        from mettagrid.builder import envs  # noqa: PLC0415

        cfg = envs.make_arena(num_agents=24, combat=True)
        simulator = Simulator()
        env = MettaGridPufferEnv(simulator, cfg)
        env.reset()
        return env
    else:
        raise ValueError(f"Unknown preset: {preset}. Available: {list(PRESET_CONFIGS.keys())}")


def main():
    parser = argparse.ArgumentParser(
        description="MettaGrid env-only performance benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Preset configs (--config):
  toy        20 agents, move+noop, 40x40 random map (fast sanity check)
  arena      24 agents, combat, production training config

For cogsguard benchmarking, use packages/cogames/benchmarks/perf/perf_benchmark.py.

Examples:
  # Run with preset config
  python perf_benchmark.py --config arena --profile

  # Run baseline measurement
  python perf_benchmark.py --phase baseline --output results/phase_0_baseline.json

  # Compare against baseline
  python perf_benchmark.py --phase phase1 --output results/phase_1.json \\
      --baseline results/phase_0_baseline.json

  # Generate summary report
  python perf_benchmark.py --report results/
        """,
    )
    parser.add_argument(
        "--config",
        type=str,
        choices=list(PRESET_CONFIGS.keys()),
        help="Use a preset config instead of --agents/--map-size/--density",
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

    if args.report:
        generate_phase_report(args.report, {}, "")
        return

    if args.profile:
        os.environ["METTAGRID_PROFILING"] = "1"

    if args.config:
        print(f"Creating environment: --config {args.config} ({PRESET_CONFIGS[args.config]})")
        env = create_env_from_preset(args.config, seed=args.seed)
    else:
        print(
            f"Creating environment: {args.agents} agents on {args.map_size}x{args.map_size} map"
            f" (density={args.density})"
        )
        env = create_env(num_agents=args.agents, map_size=args.map_size, density=args.density, seed=args.seed)
    if args.phase:
        print(f"Phase: {args.phase}")

    stats = run_performance(
        env, iterations=args.iterations, rounds=args.rounds, warmup=args.warmup, profile=args.profile
    )

    if args.output:
        if args.config:
            config = {
                "preset": args.config,
                "agents": env.num_agents,
                "iterations": args.iterations,
                "rounds": args.rounds,
                "warmup": args.warmup,
                "seed": args.seed,
            }
        else:
            config = {
                "agents": args.agents,
                "map_size": args.map_size,
                "density": args.density,
                "iterations": args.iterations,
                "rounds": args.rounds,
                "warmup": args.warmup,
                "seed": args.seed,
            }
        save_results(stats, config, args.phase, args.output)

    if args.baseline:
        print(f"\n{'=' * 60}")
        print("Comparisons")
        print(f"{'=' * 60}")
        comparisons = compare_multiple(args.baseline, stats, args.phase or "current")
        for comparison in comparisons:
            print_comparison(comparison)

        if args.output:
            with open(args.output) as f:
                result = json.load(f)
            result["comparisons"] = comparisons
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2)

    if stats["cv"] > 0.20:
        print("\nPerformance measurement unstable!")
        sys.exit(1)

    if stats.get("validation_mismatches", 0) > 0:
        print("\nObservations validation FAILED!")
        sys.exit(2)


if __name__ == "__main__":
    main()
