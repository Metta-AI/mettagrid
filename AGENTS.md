# AGENTS.md — mettagrid

Public C++/Python/Nim grid environment. No internal application dependencies. `cogames` depends on this package, so treat its public API as load-bearing.

## Development setup

This checkout contains the package sources and Bazel targets, but does not
include a Bazel workspace definition (`MODULE.bazel` or `WORKSPACE`). Its
build backend and version metadata still expect a containing workspace.
A fresh standalone checkout therefore does not provide a complete source-build
setup. Report that packaging gap before attempting native builds; do not assume
access to a separate workspace or bypass the build backend.

Once a compatible development environment and native extension are installed,
run Python tests from this repository root:

```bash
python -m pytest tests -v
```

The test dependencies are declared in the `testing` group in `pyproject.toml`.
Use the package's Bazel targets from a configured build workspace for native
tests and static analysis. Verify its target labels and configurations first.
`tests/cpplint.sh` also assumes workspace-level configuration; inspect it before
using it in a standalone checkout.

For clangd, generate `compile_commands.json` using the configured build
workspace's supported exporter. Regenerate it after build-target changes.

## Gotchas

- `build/`, `dist/`, `bazel-*`, and `.bazel_output/` are generated. Keep them out of source edits and routine searches.
- The Nim visualizer has its own conventions: see `nim/mettascope/AGENTS.md`.
- Do not modify `proto/` schemas as part of a refactor; schema changes need explicit discussion.
