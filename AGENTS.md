# AGENTS.md — mettagrid

Public C++/Python/Nim grid environment. No internal application dependencies. `cogames` depends on this package, so treat its public API as load-bearing.

## Build

`uv sync` runs the Bazel build automatically via the custom build backend — you usually don't invoke Bazel by hand.
When you need the C++ artifacts directly:

```bash
# Run from this repository root.
bazel build --config=dbg //:mettagrid_c    # debug symbols (default for dev)
bazel build --config=opt //:mettagrid_c    # optimized (use for benchmarks)
```

## Tests

```bash
bazel test //...                                          # C++ unit tests + benchmarks
uv run --group testing pytest tests -v                    # Python tests
```

## Lint

```bash
bash tests/cpplint.sh                     # C++ style (config in CPPLINT.cfg)
```

Use the lint configuration and checks supplied by this checkout; do not assume an external workspace wrapper.

C++ static analysis runs through Bazel (`lint/clang_tidy.bzl`).

## Code intelligence (clangd)

The `clangd-lsp` plugin needs a `compile_commands.json`, which Bazel does not emit by default. Generate it with:

```bash
bazel run @hedron_compile_commands//:refresh_all
```

Re-run after changing `BUILD.bazel` targets or adding C++ files.

## Gotchas

- `build/`, `dist/`, `bazel-*`, and `.bazel_output/` are generated. They are excluded from search via
  `.claude/settings.json` deny rules — don't edit or read them.
- The Nim visualizer has its own conventions: see `nim/mettascope/AGENTS.md`.
- Do not modify `proto/` schemas as part of a refactor; schema changes need explicit discussion.
