# MettaGrid Performance Optimization

Tools for profiling and benchmarking MettaGrid performance.

## Step Phases

A single `_step()` call executes these phases in order:

| Phase            | What it does                                                                            |
| ---------------- | --------------------------------------------------------------------------------------- |
| **reset**        | Zero reward/observation buffers, clear action success flags                             |
| **events**       | Increment timestep, process scheduled events                                            |
| **actions**      | Shuffle agent order, execute actions by priority, track success                         |
| **on_tick**      | Per-agent tick handlers (passives, buffs, cooldowns)                                    |
| **aoe**          | Fixed and mobile area-of-effect resolution                                              |
| **collectives**  | Update collective held stats and alignment tracking                                     |
| **observations** | Compute per-agent observation windows, encode visible entities and features into tokens |
| **rewards**      | Evaluate reward conditions, accumulate per-agent rewards                                |
| **truncation**   | Check `current_step >= max_steps`, set terminal flags                                   |

Phase costs vary by config — use `scripts/profile_multi_config.py` for per-config breakdowns. Observations typically
dominate; actions and rewards are secondary bottlenecks.

Set `METTAGRID_PROFILING=1` to enable per-phase nanosecond timing (read once at construction, zero overhead when unset,
~6% overhead when enabled). With profiling on, `env.step_timing` exposes per-step durations after each `step()` call.
The profiling infrastructure (`StepTimingStats`, `profiling.hpp`, `profiling_py.cpp`) is general-purpose and independent
of any specific optimization.

## Profiling Workflow

Start with `profile_multi_config.py` to identify which phase dominates for your config. Use
`perf_benchmark.py --profile` to measure before/after for a specific change. Use training A/B comparison to measure
end-to-end SPS impact.

C++ step time is a fraction of total training time — the rest is policy inference, gradient computation, and data
transfer. On CPU, ~6% of training time is C++ step; on GPU, ~25% estimated (rollout is a larger share). Implication: a
3x speedup on a phase that's 60% of C++ step yields only ~8% training SPS improvement on CPU.

Phase proportions shift significantly with config: obs was 68% of step at 20 agents but 89% at 100 agents (11x11
window). Profile your target config, not just the default benchmark config.

## Tools

### `perf_benchmark.py`

Env-only benchmark (no neural net, no policy inference). Measures raw environment stepping performance with random
actions.

```bash
# Basic run (SPS only, no timing breakdown)
uv run python perf_benchmark.py

# With per-phase timing (sets METTAGRID_PROFILING=1 internally)
uv run python perf_benchmark.py --profile

# Save results for comparison
uv run python perf_benchmark.py --profile --phase baseline --output results/baseline.json

# Compare against saved baseline
uv run python perf_benchmark.py --profile --phase optimized --output results/optimized.json \
    --baseline results/baseline.json

# Generate summary report from results directory
uv run python perf_benchmark.py --report results/
```

| Flag           | Default | Description                             |
| -------------- | ------- | --------------------------------------- |
| `--agents`     | 20      | Number of agents                        |
| `--map-size`   | 40      | Map width/height                        |
| `--density`    | 0.04    | Wall density (fraction of map)          |
| `--iterations` | 20,000  | Steps per measurement round             |
| `--rounds`     | 20      | Number of measurement rounds            |
| `--warmup`     | 150,000 | Warm-up steps before measurement        |
| `--seed`       | 42      | Random seed                             |
| `--profile`    | off     | Enable per-phase step timing breakdown  |
| `--output`     | none    | Save results to JSON                    |
| `--baseline`   | none    | Compare against baseline JSON file(s)   |
| `--phase`      | none    | Label for this optimization phase       |
| `--report`     | none    | Generate summary from results directory |

**Exit codes:** 0 = success, 1 = unstable measurements (CV > 20%), 2 = validation mismatches detected.

**Limitations:**

- Uses a simple config (move + noop actions, walls only). Does not exercise inventory, combat, or complex game
  mechanics.
- Random actions, not learned policy. Action distribution differs from real training.
- Phase breakdown requires `--profile`, which adds ~6% overhead. SPS without `--profile` reflects production
  performance.

### `scripts/profile_multi_config.py`

Profiles step timing across three configs: Toy (20 agents, walls only), Arena (24 agents, combat), and CogsGuard (8
agents, machina_1 layout).

```bash
uv run python scripts/profile_multi_config.py
```

No options. Prints a per-phase timing table for each config showing mean microseconds, percentage of C++ step time, and
percentage of wall-clock time (includes Python/pybind overhead). Phases contributing <1% of C++ time are omitted.

**Limitations:**

- CogsGuard config requires `recipes.experiment.cogsguard` to be importable (skipped if not available).
- Hardcoded step counts (15K steps, 5K warmup). Sufficient for stable timing but not configurable.

### `test_perf.sh`

Rebuilds mettagrid (`uv sync --reinstall-package mettagrid`) then runs `perf_benchmark.py` with any arguments passed
through.

```bash
bash test_perf.sh --profile --rounds 10
```

### Training A/B comparison

To measure training SPS impact of a change, run two training jobs on the same config differing only in the variable
under test:

```bash
# Baseline
uv run ./tools/run.py recipes.experiment.ci.train \
  trainer.total_timesteps=100000 \
  run=perf_baseline_$(date +%Y%m%d_%H%M%S)

# With change (e.g., optimized observation path)
METTAGRID_OBS_USE_OPTIMIZED=1 uv run ./tools/run.py recipes.experiment.ci.train \
  trainer.total_timesteps=100000 \
  run=perf_optimized_$(date +%Y%m%d_%H%M%S)
```

SPS data is in `train_dir/{run_name}/logs/script.log` — look for epoch lines with `sps` values.

## Observation Optimizations

Observations are the largest single phase in `_step()`. This section covers the optimized observation path and its
validation infrastructure.

### Environment Variables

| Variable                        | Effect                                                                                                      |
| ------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `METTAGRID_OBS_VALIDATION=1`    | Shadow validation: run both original and optimized observation paths, compare byte-by-byte, log mismatches. |
| `METTAGRID_OBS_USE_OPTIMIZED=1` | Use the optimized observation path as primary (default is original).                                        |

These are independent. Validation runs both paths regardless of which is primary.

When `METTAGRID_OBS_VALIDATION=1` is set, `perf_benchmark.py` also reports validation stats (comparison count, mismatch
count, timing ratio) regardless of `--profile`.

### Validation via Training

`scripts/run_training_validation.sh` runs actual training with shadow validation enabled. Uses
`recipes.experiment.ci.train` (arena_basic_easy_shaped: 2 arena.combat envs, 24 agents, 11x11 obs, 25x25 map).

```bash
# Smoke test (~1 min, ~576 comparisons/env, below reporting threshold)
METTAGRID_OBS_VALIDATION=1 METTAGRID_OBS_USE_OPTIMIZED=1 \
  bash scripts/run_training_validation.sh smoke

# Soak test (~12 min, 100K timesteps, 10K+ comparisons/env)
METTAGRID_OBS_VALIDATION=1 METTAGRID_OBS_USE_OPTIMIZED=1 \
  bash scripts/run_training_validation.sh soak

# Custom timestep count
METTAGRID_OBS_VALIDATION=1 METTAGRID_OBS_USE_OPTIMIZED=1 \
  bash scripts/run_training_validation.sh 50000
```

Validation progress is logged to stderr at 1K, 10K, and every 100K comparisons. Log file is written to
`/tmp/mettagrid_validation_*.log`.

**Limitations:**

- CI recipe uses small batches and CPU-only training. SPS numbers are not representative of production GPU throughput.
- Validation roughly halves SPS (runs both paths every step).

### Rollout Plan

**1. Validate at scale.** Run shadow validation on a production config to confirm byte-identical output:

```bash
METTAGRID_OBS_VALIDATION=1 METTAGRID_OBS_USE_OPTIMIZED=1 \
  uv run ./tools/run.py <production_recipe> \
  trainer.total_timesteps=<sufficient_for_100K+_comparisons> \
  run=obs_validation_prod_$(date +%Y%m%d_%H%M%S)
```

Pass criteria: 0 mismatches in validation log output.

**2. Measure production training impact.** Compare SPS with and without `METTAGRID_OBS_USE_OPTIMIZED=1` on the same
production config. On GPU servers, rollout is a larger fraction of total training time (~25% estimated vs ~6% on
CPU-only), so the 2.7-3.5x observation speedup should yield a measurable training throughput improvement.

**3. Make optimized path the default.** Remove `_compute_observation_original()` and the dispatcher. Rename
`_compute_observation_optimized()` to `_compute_observation()`. Remove the `METTAGRID_OBS_USE_OPTIMIZED` env var.

**4. Remove validation infrastructure.** Remove `_shadow_validate_observation()`, `_shadow_obs_buffer`,
`ObsValidationStats`, and the `METTAGRID_OBS_VALIDATION` env var.
