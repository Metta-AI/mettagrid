# MettaGrid Action System - Technical Manual

This document provides a technical explanation of the action format that policies should emit when interacting with
MettaGrid. It covers the discrete action space structure, action ID assignment, action types, and how policies should
produce actions.

> For information about using actions via the Python Simulator API (e.g., `agent.set_action()`, `Action`), see
> [simulator_api.md](simulator_api.md#action-system).

## Overview

MettaGrid uses a **discrete action space** where actions are represented as a single integer index (action ID). Each
action ID corresponds to a fully qualified action variant such as `move_north`, `move_east`, or `change_vibe_happy`.
Verb/argument combinations are flattened during environment construction, so policies only need to emit a scalar
`action_id` per agent.

## Action Space Structure

### Action Format

Actions are provided as NumPy arrays with shape `(num_agents,)`:

- **Type**: `int32` (or `np.int32`)
- **Range**: `0 <= action_id < num_actions`
- **Per agent**: Each agent emits a single action ID

### Action ID Assignment

Action IDs are assigned sequentially starting from 0 based on the order in which actions are registered during
environment construction. The exact action set depends on the game configuration (enabled actions, allowed directions,
etc.).

> Action IDs may differ between configurations. Policy authors should either ensure that the same action configuration
> exists between training and evaluation, or should ensure that trained policies can appropriately deal with changing
> action IDs (e.g., by accepting action names and mapping them to IDs dynamically).

### Getting Action Information from Configuration

Action names can be obtained directly from configuration:

```python
from mettagrid.config.mettagrid_config import MettaGridConfig

config = MettaGridConfig(...)

# Get action names from config
action_names = [action.name for action in config.game.actions.actions()]

# Or from an instantiated Simulation
from mettagrid.simulator import Simulator

simulator = Simulator()
sim = simulator.new_simulation(config, seed=0)

action_ids = sim.action_ids  # dict[str, int] e.g., {"noop": 0, "move_north": 1, ...}
action_names = sim.action_names  # list[str] e.g., ["noop", "move_north", "move_south", ...]
num_actions = len(action_names)
```

## Action Types

The following action types are available in MettaGrid. The exact set depends on your game configuration.

### Noop Action

- **Name**: `noop`
- **Description**: Do nothing. Always available and typically has action ID 0.
- **Resource requirements**: None

### Move Actions

- **Name pattern**: `move_{direction}`
- **Directions**: `north`, `south`, `east`, `west` (and optionally `northeast`, `northwest`, `southeast`, `southwest` if
  diagonals are enabled). Moving into an object triggers interaction with that object.
- **Description**: Move the agent one cell in the specified direction
- **Resource requirements**: Consumes energy (configurable)

Example action names:

- `move_north`
- `move_south`
- `move_east`
- `move_west`

### Change Vibe Actions

- **Name pattern**: `change_vibe_{vibe_name}`
- **Vibes**: Depends on configuration (e.g., `happy`, `sad`, `angry`, etc.)
- **Description**: Change the agent's current vibe to the specified vibe. Vibes can be used for communication, and also
  impacts environmental interactions.

Example action names:

- `change_vibe_happy`
- `change_vibe_sad`
- `change_vibe_neutral`

> **Note**: The available vibes are configurable via `change_vibe.vibes`.

### Attack Actions

- **Description**: Attack triggers via movement onto another agent (when vibes match), not as a standalone action. On success the attacker can transfer inventory and loot resources. Targets can defend if they hold sufficient defense resources; weapon and armor inventories modify the defense cost threshold. Per-vibe armor bonuses are supported.
- **Configuration**: `attack.defense_resources`, `attack.armor_resources`, `attack.weapon_resources`, `attack.success` (inventory deltas, loot), `attack.vibes`, `attack.vibe_bonus`, `attack.enabled`.

## Policy Action Emission

Policies should subclass `MultiAgentPolicy`. For training, where batch processing is most important, the `step_batch`
method will be called.

```python
from mettagrid.policy.policy import MultiAgentPolicy
import numpy as np
from mettagrid.mettagrid_c import dtype_actions

class MyMultiAgentPolicy(MultiAgentPolicy):
    def step_batch(self, raw_observations: np.ndarray, raw_actions: np.ndarray) -> None:
        """
        Process batch of observations and write actions to output buffer.

        Args:
            raw_observations: Observation array with shape (num_agents, num_tokens, 3)
            raw_actions: Output buffer with shape (num_agents,) - write actions here as int32
        """
        num_agents = raw_observations.shape[0]

        for agent_id in range(num_agents):
            # Extract observation tokens for this agent
            obs_tokens = raw_observations[agent_id]

            # Your policy logic here (e.g., neural network forward pass)
            action_id = self.select_action(obs_tokens)

            # Write action ID directly to the output buffer
            raw_actions[agent_id] = dtype_actions.type(action_id)
```

The `step_batch` method receives:

- **`raw_observations`**: NumPy array with shape `(num_agents, num_tokens, 3)` containing observation tokens
- **`raw_actions`**: NumPy array with shape `(num_agents,)` - policies should write action IDs here as `int32` values

Actions are written directly into the `raw_actions` buffer, which is then used by the environment. This allows for
efficient batch processing without creating intermediate `Action` objects.

## Action Execution Flow

When an action is executed, the following validation occurs:

1. **Action Index Validation**: `0 <= action_id < num_actions`
2. **Action Space Validation**: Action ID must be within `env.action_space.n`
3. **Agent State Validation**: Agent must not be frozen
4. **Resource Validation**: Agent must have required resources (if any)
5. **Action Execution**: Attempt the action

### Invalid Actions

If an action is invalid (out of range, insufficient resources, etc.), the action is silently ignored and the agent
effectively performs a noop.
