#!/bin/bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"

echo "==> Rebuilding mettagrid package (builds .so via bazel_build.py)..."
uv sync --reinstall-package mettagrid --directory "$REPO_ROOT"

echo "==> Running performance test..."
uv run --directory "$REPO_ROOT" python \
  "$REPO_ROOT/packages/mettagrid/benchmarks/perf/perf_benchmark.py" "$@"
