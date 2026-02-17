# Replay Format Specification

MettaScope uses a custom replay format to store the replay data. The replay is a zlib compressed json file with
`.json.z` extension.

Here is an example of how to decompress the file, from python:

```python
file_name = "replay.json.z"
with open(file_name, "rb") as file:
    compressed_data = file.read()
decompressed_data = zlib.decompress(compressed_data)
json_data = json.loads(decompressed_data)
```

In JavaScript it's a bit more complicated, but you can use the `decompressStream` with a streaming API.

## Version Management

The first key in the format is `version`, which is a number that contains the version of the replay format.

```json
{
  "version": 5,
  ...
}
```

Mettascope can only support a single version of the replay format at a time. If it encounters a replay with a different
version, it will show a dialog with a button to open the previous build in a browser with that URL.

Builds are stored at:

`https://softmax-public.s3.amazonaws.com/mettascope/$version`

So if the replay format is `5`, but he app only supports `6` the app will redirect to
`https://softmax-public.s3.amazonaws.com/mettascope/5/mettascope.html?replay=...`.

## The Top-Level Keys

These are the constants that are stored at the top of the replay.

- `num_agents` - The number of agents in the replay.
- `max_steps` - The maximum number of steps in the replay.
- `map_size` - The size of the map. No object may move outside of the map bounds.
- `file_name` - The name of the replay file. This helps identify the replay when processing multiple files.

```json
{
  ...
  "num_agents": 24,
  "max_steps": 1000,
  "map_size": [62, 62],
  "file_name": "example_replay.json.z",
  ...
}
```

There are several key-to-string mapping arrays stored in the replay. Objects refer to these mappings by using
lightweight identifiers: `type_name` must match an entry in `type_names`, while `action_id`, `items`, and `group_id`
remain numeric indices into `action_names`, `item_names`, and `group_names` respectively. Legacy replays may still
include a numeric `type_id`, but new data should rely on the string `type_name` field.

```json
{
  ...
  "type_names": ["agent", "wall", "hub", ... ],
  "action_names": ["noop", "move", "rotate", ... ],
  "item_names": ["hearts", "coconuts", ... ],
  "group_names": ["group1", "group2", ... ],
  "collective_names": ["clips", "cogs", ... ],
  "tags": {"type:agent": 0, "type:hub": 1, "type:wall": 2, ... },
  ...
}
```

The `collective_names` array (added in version 4) maps collective IDs to names. The array index corresponds to the
collective ID, matching the C++ implementation which assigns IDs based on sorted alphabetical order of names.

The `tags` object maps tag names to tag IDs. Tags are assigned IDs based on sorted alphabetical order of all unique tag
names collected from the game configuration (game-level tags, object tags, agent tags, and auto-generated `type:` tags).
Each grid object includes a `tag_ids` field containing the list of tag IDs assigned to it.

The `capacity_names` array maps capacity group IDs to names. Each index is a `capacity_id` used in per-object
`inventory_capacities` time series. Built from the inventory limit group names in the agent config, sorted
alphabetically for determinism. Example: `["cargo", "energy", "gear", "heart"]`. Multiple resources can share a single
capacity group (e.g., different ore types share the "cargo" capacity pool).

## Objects and time series

The most important key in the format is `objects` which is a list of objects that are in the replay. Everything is an
object - walls, buildings, and agents.

```json
{
  ...
  "objects": [
    {...},
    {...},
    {...},
    ...
  ],
  ...
}
```

Objects are stored in a condensed format. Every field of the object is either a constant or a time series of values.

**Time series fields** can be represented in two ways:

1. **Single value** - When the field never changes during the replay, it's stored as just the value.
2. **Time series array** - When the field changes, it's stored as a list of tuples where the first element is the step
   and the second element is the value.

The time series array format uses tuples where the first element is the step and the second element is the value, which
can be a number, boolean, or a list of numbers.

```json
{
  "id": 99,
  "alive": [[0, true], [100, false]],
  "type_name": "agent",
  "agent_id": 0,
  "rotation": [[0, 1], [10, 2], [20, 3]],
  "location": [[0, [10, 10]], [1, [11, 10]], [2, [12, 11]]],
  "inventory": [[0, []], [100, [1]], [200, [1, 1]]],
  ...
}
```

Alive represents whether the object is alive or not. It starts out alive on step 0 and then dies at step 100. In this
example, the agent `type_name` is `"agent"`, which must appear in the `type_names` array. Legacy files might also
include a numeric `type_id`; when present it maps into `type_names[type_id]`. The mapping between entries and names can
change between replays. The `id` is a constant as well. All objects have IDs. The `agent_id` is a constant as well. Note
there are two IDs, one for the object and one for the agent. Agents have two IDs. The `rotation` is a time series of
values. The rotation is 1 at step 0, 2 at step 10, and 3 at step 20.

Here is the expanded version of the `rotation` key:

```json
{
  "rotation": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3]
}
```

You can either expand the whole time series on load or use binary search to find the value at a specific step. At first
I was using binary search, but expanding the time series is much faster. This is up to the implementation.

The `location` key is a time series of tuples, where the first element is the step and the second element is the
location, which is a list of two numbers for x and y.

The `inventory` key is a time series of tuples, where the first element is the step and the second element is the list
of item_IDs. It starts empty and then adds items at steps 100, 200, etc.

As another example, if the `rotation` key was always 1, it could also be stored simply as `"rotation": 1`.

## Key reference

Here are the keys supported for both agents and objects:

- `id` - The id of the object.
- `alive` - Boolean time series indicating whether the object is alive. When an object is removed from the simulation
  (e.g., a depleted extractor), `alive` transitions to `false`. Objects can become alive again if they reappear.
  Defaults to `true` if missing. Example: `[[0, true], [100, false]]` means alive from step 0, removed at step 100.
- `type_name` - The type of the object; its value must be present in the `type_names` array. Legacy data may include a
  numeric `type_id` as an additional field mapping into the same array.
- `location` - The [x, y] location of the object (sometimes called the column and row).
- `orientation` - The rotation of the object.

- `inventory` - The current list of item amounts that map to the `item_names` array. Array of `[item_id, count]` pairs.
  Example: `[[0, 2], [1, 1]]`. If `item_names = ["hearts", "bread"]`, then inventory is 2 hearts and 1 bread.

  Note: In the replay data, this is represented in the `inventory` field as a time series showing how inventory changes
  over time (e.g., `[[0, []], [100, [[1, 1]]], [200, [[1, 2]]]]`), where each entry contains a timestamp and the
  inventory state at that time and into the future.

- `inventory_max` - Maximum number of items that can be in the inventory. (Legacy; superseded by `inventory_capacities`
  for per-group limits.)
- `inventory_capacities` - Per-capacity-group effective limits as `[[capacity_id, effective_limit], ...]` pairs. Each
  `capacity_id` is an index into the top-level `capacity_names` array. This is a time series that changes as agents
  equip/unequip modifier items (e.g., picking up gear increases cargo capacity). Resources sharing a capacity group draw
  from the same pool. Example: `[[0, 20], [2, 10]]` means capacity group 0 has effective limit 20 and capacity group 2
  has effective limit 10. As a time series: `[[0, [[0, 20], [2, 10]]], [50, [[0, 15], [2, 10]]]]` means at step 50,
  capacity group 0 decreased to 15.
- `color` - The color of the object. Must be an integer between 0 and 255.
- `tag_ids` - List of tag IDs assigned to this object. These reference the `tags` mapping in the top-level replay data.
  Tags can change during gameplay (e.g., via tag mutations), so this is a time series field. Example: `[0, 2, 5]` means
  the object has the tags at indices 0, 2, and 5 in the `tags` mapping.

- `collective_id` - The collective (team/faction) this object belongs to. This is a time series value that can change
  during gameplay (e.g., when a junction is captured by a different team). Valid values:
  - `0` = Clips (red team)
  - `1` = Cogs (green team)
  - `-1` = Neutral/undefined (not aligned with any collective)

  Objects like junctions can switch collective ownership during a game, which is why this field is tracked as a time
  series rather than a constant.

Agent specific keys:

- `agent_id` - The id of the agent.
- `action_id` - The action of the agent that references the `action_names` array.
- `action_parameter` - Single value for the action. If `action_names[action_id] == "rotate"` and
  `action_parameter == 3`, this means move to the right. The implementation does not need to know this as it can be
  inferred from the rotation and x, y positions.
- `action_success` - Boolean value that indicates if the action was successful.
- `total_reward` - The total reward of the agent.
- `current_reward` - The reward of the agent for the current step.
- `frozen` - Boolean value that indicates if the agent is frozen.
- `frozen_progress` - A countdown from `frozen_time` to 0 that indicates how many steps are left to unfreeze the agent.
- `frozen_time` - How many steps does it take to unfreeze the agent.
- `group_id` - The id of the group the object belongs to.

Keys are allowed to be missing. If a key is missing, missing keys are always 0, false, or []. Extra keys are ignored but
can be used by later implementations. If a time series starts from some other step like 100, then the first 99 steps are
just the default value.

## Version 4 additions

Version 4 adds several new top-level keys for enhanced replay analysis and debugging.

### policy_env_interface

Contains the policy environment interface configuration, describing observation features and action space. This helps
replay consumers understand how agents perceive the environment.

```json
{
  "policy_env_interface": {
    "obs_features": [
      {"id": 0, "name": "agent:group", "normalization": 10.0},
      {"id": 1, "name": "agent:frozen", "normalization": 1.0},
      {"id": 2, "name": "episode_completion_pct", "normalization": 255.0},
      {"id": 3, "name": "last_action", "normalization": 10.0},
      {"id": 4, "name": "last_reward", "normalization": 100.0}
    ],
    "tags": ["arena", "competitive"],
    "action_names": ["noop", "move", "rotate", ...],
    "move_energy_cost": 1.0,
    "num_agents": 24,
    "observation_shape": [11, 11, 32],
    "egocentric_shape": [11, 11]
  }
}
```

### infos

Contains episode-level statistics and metadata, populated at episode end. Useful for analyzing agent performance and
game outcomes.

```json
{
  "infos": {
    "game": {
      "objects.wall": 1384.0,
      "objects.agent.agent": 24.0,
      "tokens_written": 65650.0,
      "tokens_dropped": 0.0
    },
    "agent": {
      "heart.amount": 0.0,
      "ore_red.amount": 0.0,
      "action.noop.success": 100.0
    },
    "collective": {
      "clips": {"score": 150.0},
      "cogs": {"score": 120.0}
    },
    "attributes": {
      "seed": 609250,
      "map_w": 62,
      "map_h": 62,
      "steps": 100,
      "max_steps": 100
    },
    "episode_rewards": [0.0, 0.0, ...]
  }
}
```

- `game` - Game-level statistics (object counts, token stats)
- `agent` - Agent statistics averaged across all agents
- `collective` - Per-collective (team) statistics, if present
- `attributes` - Episode metadata (seed, map size, step counts)
- `episode_rewards` - Final reward for each agent (indexed by agent_id)

### collective_inventory

Time-series tracking of inventory for each collective (team). Format is an array where the index corresponds to the
collective ID (matching the `collective_names` array). Each element is a time-series array of
`[step, [[item_id, count], ...]]` pairs, using item IDs that index into the `item_names` array.

```json
{
  "collective_inventory": [
    [
      [
        0,
        [
          [0, 0],
          [1, 0]
        ]
      ],
      [
        50,
        [
          [0, 10],
          [1, 5]
        ]
      ],
      [
        100,
        [
          [0, 25],
          [1, 12]
        ]
      ]
    ],
    [
      [
        0,
        [
          [0, 0],
          [1, 0]
        ]
      ],
      [
        50,
        [
          [0, 8],
          [1, 7]
        ]
      ]
    ]
  ]
}
```

Where `collective_names = ["clips", "cogs"]` and `item_names = ["hearts", "ore_red", ...]`, so index 0 is "clips" and
`[0, 10]` means 10 hearts.

Only records changes - if inventory doesn't change between steps, no entry is added.

## Realtime WebSocket

This format extends into real time with some differences. Instead of getting a compressed JSON file, you connect to a
WebSocket and get replay format as a stream of messages. Each message can omit keys and only send them if they changed.
You can then take the current replay you have and extend it with the new message. Each message has a new step field:

````json
{
  "step": 100,
  "version": 2,
  ...
  "objects": [
    {...},
    {...},
    {...},
    ...
  ],
}

In this format there are no time series for the object properties. Instead everything is a constant that happens at the specific step.

On step 0:

```json
{
  "type_name": "agent",
  "id": 99,
  "agent_id": 0,
  "rotation": 3,
  "location": [12, 11],
  "inventory": [1, 1],
  ...
}
````

On later steps, only the `id` is required and any changed keys are sent. Many keys like `type_name`, `agent_id`,
`group_id`, etc. don't change so they are only sent on step 0. While other keys like `location`, `inventory`, etc. are
sent every time they change.

```json
{
  "id": 99,
  "location": [12, 11],
  "inventory": [1, 1],
  ...
}
```

If no properties change, there is no need to send the object at all. Many static objects like walls are only spent on
step 0.
