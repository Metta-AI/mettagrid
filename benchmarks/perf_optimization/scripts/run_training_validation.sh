#!/usr/bin/env bash
# Run actual training with shadow validation enabled.
#
# Uses recipes.experiment.ci.train (arena_basic_easy_shaped config):
#   2 arena.combat envs, 24 agents, 11x11 obs, 25x25 map
#   ~2M trainable params, ~145 SPS with policy inference
#
# Usage:
#   # Smoke test (CI defaults, ~576 comparisons/env, finishes in ~1 min):
#   METTAGRID_OBS_VALIDATION=1 METTAGRID_OBS_USE_OPTIMIZED=1 \
#     bash packages/mettagrid/benchmarks/perf_optimization/scripts/run_training_validation.sh smoke
#
#   # Soak test (100K timesteps, ~10K comparisons/env, ~12 min):
#   METTAGRID_OBS_VALIDATION=1 METTAGRID_OBS_USE_OPTIMIZED=1 \
#     bash packages/mettagrid/benchmarks/perf_optimization/scripts/run_training_validation.sh soak
#
#   # Custom timesteps:
#   METTAGRID_OBS_VALIDATION=1 METTAGRID_OBS_USE_OPTIMIZED=1 \
#     bash packages/mettagrid/benchmarks/perf_optimization/scripts/run_training_validation.sh 50000
#
# Prerequisites:
#   - Rebuild mettagrid if switching branches:
#       uv sync --reinstall-package mettagrid
#   - Set env vars:
#       METTAGRID_OBS_VALIDATION=1   (enable shadow validation)
#       METTAGRID_OBS_USE_OPTIMIZED=1 (use optimized path as primary)
#
# Validation logs appear at 1K, 10K, and every 100K comparisons:
#   [METTAGRID OBS_VALIDATION] 1000 comparisons, 0 mismatches, timing ratio=1.55x
#
# Branches:
#   monica/obs-perf-validation    - validation framework (original is primary)
#   monica/obs-perf-optimizations - optimizations (optimized is primary when USE_OPTIMIZED=1)
#
# Reproduces results from PR comments on #6641 and #6642.
#
# Original experiments (2026-02-06):
#   Smoke: recipes.experiment.ci.train run=obs_validation_smoke
#          → 576 comparisons/env, below 1K threshold, no timing output
#   Soak:  recipes.experiment.ci.train trainer.total_timesteps=100000 run=obs_validation_soak
#          → 0 mismatches, timing ratio 1.52x/1.58x at 10K, ~145 SPS, 87 epochs

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
MODE="${1:-soak}"

case "${MODE}" in
  smoke)
    # Smoke test: use CI recipe defaults (sandbox=true auto-applied by ci recipe)
    # Runs briefly, ~576 comparisons/env, below 1K reporting threshold
    RUN_NAME="obs_validation_smoke_$(date +%Y%m%d_%H%M%S)"
    EXTRA_ARGS="run=${RUN_NAME}"
    ;;
  soak)
    # Soak test: 100K timesteps, reaches 10K+ comparisons per env
    RUN_NAME="obs_validation_soak_$(date +%Y%m%d_%H%M%S)"
    EXTRA_ARGS="trainer.total_timesteps=100000 run=${RUN_NAME}"
    ;;
  *)
    # Custom timestep count
    RUN_NAME="obs_validation_custom_$(date +%Y%m%d_%H%M%S)"
    EXTRA_ARGS="trainer.total_timesteps=${MODE} run=${RUN_NAME}"
    ;;
esac

echo "========================================"
echo "Training validation run"
echo "  Mode: ${MODE}"
echo "  Branch: $(git branch --show-current)"
echo "  Run name: ${RUN_NAME}"
echo "  METTAGRID_OBS_VALIDATION=${METTAGRID_OBS_VALIDATION:-unset}"
echo "  METTAGRID_OBS_USE_OPTIMIZED=${METTAGRID_OBS_USE_OPTIMIZED:-unset}"
echo "========================================"

if [[ "${METTAGRID_OBS_VALIDATION:-}" != "1" ]]; then
  echo "WARNING: METTAGRID_OBS_VALIDATION not set to 1. No validation will occur."
  echo "  Run with: METTAGRID_OBS_VALIDATION=1 METTAGRID_OBS_USE_OPTIMIZED=1 $0 ${MODE}"
fi

cd "${REPO_ROOT}"

# shellcheck disable=SC2086
uv run ./tools/run.py recipes.experiment.ci.train \
  ${EXTRA_ARGS} \
  2>&1 | tee "/tmp/mettagrid_validation_${RUN_NAME}.log"

echo ""
echo "========================================"
echo "Validation log lines:"
echo "========================================"
grep -i "METTAGRID OBS_VALIDATION" "/tmp/mettagrid_validation_${RUN_NAME}.log" || echo "(no validation lines found)"
