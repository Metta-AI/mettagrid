# MettaGrid Environment

MettaGrid is a multi-agent gridworld environment for studying the emergence of cooperation and social behaviors in
reinforcement learning agents. The environment features a variety of objects and actions that agents can interact with
to manage resources, engage in combat, and optimize their rewards.

## Requirements

- Bazel 9.0.0 or newer (the project uses Bzlmod and modern Bazel features)
- Python 3.12
- C++ compiler with C++20 support

## Overview

In MettaGrid, agents navigate a gridworld and interact with various objects to manage resources, engage in combat, and
cooperate with other agents. The key dynamics include:

- **Resource Management**: Agents carry an inventory of typed resources with configurable capacity limits. Resources can
  be gathered from objects, consumed by actions, and stolen through combat.
- **Combat**: Agents can attack other agents by moving into them when their vibe matches an attack configuration.
  Successful attacks freeze the target and allow the attacker to steal resources. Targets can defend using armor and
  defense resources.
- **Vibes**: Each agent has a vibe that determines how they interact with other agents on contact. Vibes affect which
  attacks trigger, defense bonuses, and are visible in observations.

The environment is highly configurable, allowing for experimentation with different world layouts, object placements,
game mechanics, and agent capabilities.

## Objects

### Agent

The `Agent` object represents an individual agent in the environment. Agents can move, attack, change their vibe, and
interact with other objects. Each agent has an inventory, a vibe, and a frozen state that govern its abilities and
interactions.

### Wall

The `Wall` object acts as an impassable barrier in the environment, restricting agent movement.

### Custom Objects

Object types beyond Agent and Wall are defined entirely through configuration. Any object can have an inventory, on-use
handlers that trigger when an agent moves into them, area-of-effect behaviors that apply to nearby objects each tick,
and territory controls.

## Actions

### Move

The `move` action allows agents to move to an adjacent cell in the gridworld. Movement supports up to 8 directions (4
cardinal and 4 diagonal), configured via `allowed_directions`. Moving into different targets triggers different
behaviors:

- Moving into an empty cell moves the agent normally.
- Moving into an object with an on-use handler triggers that handler (e.g., gathering resources from a generator).
- Moving into a frozen agent swaps positions with them.
- Moving into an agent whose vibe matches an attack configuration triggers the attack.
- Otherwise, the movement fails.

### Attack

Attacks are not standalone actions. They trigger when a move lands on an agent whose vibe matches an attack handler
configuration. The attack system uses weapon, armor, and defense resource calculations:

- Weapon power is computed from the attacker's inventory, weighted by configured amounts.
- Armor power is computed from the target's inventory, with optional vibe-based bonuses.
- If the target has sufficient defense resources, the attack is blocked and those resources are consumed.
- On a successful attack, the target is frozen for a configured duration and inventory loot is transferred to the
  attacker.

### Change Vibe

The `change_vibe` action sets the agent's current vibe. There is one action variant per configured vibe, named after the
vibe (e.g., `change_vibe_default`, `change_vibe_junction`). Changing vibe always succeeds.

### Noop

The `noop` action is a no-operation. It always succeeds with no side effects.

## Handler System

Game logic in MettaGrid is driven by an event-based handler architecture rather than hardcoded per-object behavior. This
makes the environment highly composable and configurable.

A **handler** pairs a chain of filters with a chain of mutations. All filters must pass for the mutations to execute.
Handlers are used for on-use interactions (when an agent moves into an object) and area-of-effect behaviors (applied to
nearby objects each tick).

A **multi-handler** dispatches to multiple handlers with either first-match or apply-all semantics.

**Filters** gate whether a handler's mutations execute. Available filter types include vibe matching, resource
thresholds, tag membership, shared tags between actor and target, game value thresholds, distance checks, and boolean
combinators (negation and disjunction).

**Mutations** modify game state when a handler fires. Available mutation types include resource deltas, resource
transfers between entities, freezing agents, clearing inventories, weapon-vs-armor attack calculations, stat logging,
tag modifications, and inventory queries across multiple objects.

**Events** fire at specific timesteps, applying mutations to objects matching a query. An event scheduler efficiently
dispatches these with minimal overhead when no events are due.

## Configuration

The MettaGrid environment is highly configurable through Pydantic-based configuration classes. The top-level
`MettaGridConfig` contains:

- Game rules and episode length
- Action definitions (move, attack, change vibe, noop) with per-action resource requirements
- Agent properties including group, freeze duration, initial inventory, rewards, and per-tick handlers
- Object type definitions with on-use handlers, area-of-effect configs, territory controls, and inventory
- Handler and event definitions with filter and mutation chains
- Observation feature configuration
- Map generation settings

### Map Generation

MettaGrid includes a procedural map generation system. The `MapBuilder` base class has implementations for ASCII-based
maps and random generation. The `MapGen` system provides advanced scene-based procedural generation with composable
scene types including biomes (forest, desert, caves, city), shape generators (BSP, maze, spiral, wave function
collapse), and transformations (mirror, rotate, copy). Pre-built map configurations are available in `configs/maps/`.

## Environment Architecture

### Core Simulation

The `Simulation` class provides the core simulation for running MettaGrid episodes. It offers direct access to the
simulation without an environment API — use it when you need fine-grained control over simulation steps, agent actions,
and state inspection. The `Simulator` class is a factory that creates `Simulation` instances with map caching and event
handler support.

### Environment Adapters

**`MettaGridPufferEnv`** is the primary PufferLib-compatible environment used by the Metta training system. It provides
the standard `reset()`/`step()` API with stats collection and supervisor policy support.

**`MettaGridPettingZooEnv`** is a PettingZoo ParallelEnv adapter for multi-agent research with standard dict-based
observation and action interfaces.

### Visualization

**Mettascope** is a Nim-based GUI viewer for simulation replay and real-time visualization, built as part of the
package. **Miniscope** provides a terminal-based renderer with
symbol-based map display.

### Compatibility Testing Demos

These demos ensure external framework adapters remain functional as the core environment evolves:

```bash
# Verify PettingZoo compatibility
python -m mettagrid.demos.demo_train_pettingzoo

# Verify PufferLib compatibility
python -m mettagrid.demos.demo_train_puffer
```

The demos serve as regression tests to catch compatibility issues during core development, ensuring external users can
continue using their preferred frameworks.

## Building and Testing

For local development, refer to the top-level [README.md](../README.md) in this repository.

### Bazel

By default, `uv sync` will run the Bazel build automatically via the custom build backend. If you need to run C++ tests
and benchmarks directly, you'll need to invoke `bazel` directly.

Build C++ tests and benchmarks in debug mode:

```sh
# Build with debug flags
bazel build --config=dbg //:mettagrid_c
# Run all tests
bazel test //...
```

For benchmarks you might prefer to use the optimized build:

```sh
# Build with optimizations
bazel build --config=opt //:mettagrid_c
```

For a single-core benchmark of MettaGrid performance (triggers a rebuild on first run):

```bash
bash benchmarks/perf/run.sh                    # toy config (default)
bash benchmarks/perf/run.sh --config arena      # production training config
```

## Debugging C++ Code

MettaGrid is written in C++ with Python bindings via pybind11. You can debug C++ code directly in VSCode/Cursor by
setting breakpoints in the C++ source files.

### Prerequisites

1. **VSCode Extension**: Install the
   [Python C++ Debugger](https://marketplace.visualstudio.com/items?itemName=benjamin-simmonds.pythoncpp-debug)
   extension (`pythoncpp`)
2. **Debug Build**: Always build with `DEBUG=1` to enable debug symbols and dSYM generation

### Setup

The repository includes pre-configured launch configurations in `.vscode/launch.json`:

- **MettaGrid Demo** and other pythoncpp configurations - Combined Python + C++ debugging session for the demo script
  (requires the pythoncpp extension)
- **\_C++ Attach** - Attach C++ debugger to any running Python process (shared by all configurations but can be ran
  manually).

### Quick Start

1. **Build with debug symbols**:
   - Clean everything up

     ```sh
     cd packages/mettagrid # (from root of the repository)
     bazel clean --expunge
     ```

   - Rebuild with debug flags

     ```sh
     bazel build --config=dbg //:mettagrid_c
     ```

   - Or Reinstall with DEBUG=1 to trigger dSYM generation

     ```sh
     cd ../..
     export DEBUG=1
     uv sync --reinstall-package mettagrid
     ```

2. **Set breakpoints** in both Python and C++ files (e.g., `packages/mettagrid/cpp/bindings/mettagrid_c.cpp`,
   `packages/mettagrid/demos/demo_train_pettingzoo.py`)

3. **Launch debugger** using the "MettaGrid Demo" or any other pythoncpp configuration from the VSCode Run panel.

4. **Alternatively**, you can use the "\_C++ Attach" configuration to attach the debugger to any running Python process.
   It will ask you to select a process - type "metta" or "python" to filter the list.

### Testing C++ Debugging

To verify that C++ breakpoints are working correctly, use a simple test that calls from Python into C++:

#### Quick Test Method

1. **Add a test call** to any Python entrypoint that uses mettagrid:

   ```python
   def test_cpp_debugging() -> None:
       """Test function to trigger C++ code for debugging."""
       try:
           from mettagrid.mettagrid_c import PackedCoordinate

           # Call a simple C++ function
           packed = PackedCoordinate.pack(5, 10)
           print(f"C++ test: PackedCoordinate.pack(5, 10) = {packed}")

           # Unpack it back
           r, c = PackedCoordinate.unpack(packed)
           print(f"C++ test: PackedCoordinate.unpack({packed}) = ({r}, {c})")
       except Exception as e:
           print(f"C++ debugging test failed: {e}")

   # Call at module level or early in your script
   test_cpp_debugging()
   ```

2. **Set a C++ breakpoint** in the corresponding C++ implementation:
   - Open `packages/mettagrid/cpp/include/mettagrid/systems/packed_coordinate.hpp`
   - Find the `pack()` or `unpack()` function implementation
   - Set a breakpoint inside the function body (e.g., on the return statement)

3. **Launch your debug configuration** (e.g., "MettaGrid Demo" or any pythoncpp configuration)

4. **Verify the breakpoint hits** when the Python code calls `PackedCoordinate.pack()`

#### Where to Add the Test

Add the test call early in any Python entrypoint that uses mettagrid:

- Demo scripts (e.g., `packages/mettagrid/demos/demo_train_*.py`)
- CLI entrypoints (e.g., `packages/cogames/src/cogames/main.py`)
- Tool runners (e.g., `common/src/metta/common/tool/run_tool.py`)
- Training scripts (e.g., `metta/tools/train.py`)

**Note**: This test is only for verifying your debugging setup. Remove it before committing.

### Configuration Files

- **`.bazelrc`** - Defines the `--config=dbg` build mode with debug flags (`-g`, `-O0`, `--apple_generate_dsym`)
- **`.vscode/launch.json`** - Contains launch configurations for combined Python/C++ debugging

### Important Notes

- **Always use `DEBUG=1`**: Without this environment variable, dSYM files won't be generated and C++ breakpoints won't
  work.
- **Source maps**: The launch config includes source maps to correctly locate C++ files in the packages/mettagrid's
  workspace.
