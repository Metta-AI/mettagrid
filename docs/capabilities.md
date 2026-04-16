# Mettagrid Game-Author Capabilities

> Engine primitives game-builders can compose into mechanics without writing C++. Each section covers what it does, when
> to use it, when not to, and the canonical Python config.

## Queries (target selection)

Queries find sets of objects on the grid. Used as `target_query` in events, or as sub-expressions in filters and
mutations.

### Query / query()

Tag-based lookup with optional filters. The workhorse for "find all objects of type X."

```python
query("type:hub", filters=[maxDistance(3)])
```

- `source`: Tag name or sub-query
- `filters`: List of filters (all must match)
- `max_items`: Optional limit (int or GameValue)
- `order_by`: Optional `"random"` for randomized selection

### MaterializedQuery / materializedQuery()

Pre-computes query results as a tag on matching objects. Useful when multiple systems need the same query result without
re-evaluating it each time.

```python
materializedQuery("network_member", query("type:hub", filters=[isNear(query("type:cable"), radius=1)]))
```

- `tag`: Output tag name applied to matched objects
- `query`: The query to materialize
- Computed at init; recompute with `RecomputeMaterializedQueryMutation`

### ClosureQuery / closureQuery()

BFS expansion through connected objects. Use for network/chain mechanics (e.g., connected power grids, supply lines).

```python
closureQuery(
    source=query("type:generator"),
    candidates=query("type:cable"),
    edge_filters=[maxDistance(1)],
)
```

- `source`: Seed objects for BFS
- `candidates`: Pool of objects that can join the network
- `edge_filters`: Binary filters `(net_member, candidate) -> bool`
- `filters`: Unary filters on final result set

### RaycastQuery / raycastQuery()

Walk rays from source objects in specified directions, stopping at blockers. Use for directional/line-of-sight mechanics
(blast arms, beams, projectiles, sightlines).

```python
raycastQuery(
    source=query("type:bomb"),
    max_range=3,
    directions=["north", "south", "east", "west"],
    blocker=[hasTag("type:wall")],
)
```

- `source`: Query finding ray origin objects
- `max_range`: Max cells per ray (int or GameValue, default 2)
- `directions`: Ray directions (default: 4 cardinal). Supports all 8 compass directions.
- `blocker`: Filters identifying ray-blocking objects (OR semantics -- any match stops the ray)
- `include_blocker`: Whether the first blocker is included in results (default True)

## Filters (per-target gating)

Filters gate handler and query execution. All filters have a `target` field (ACTOR or TARGET) unless noted.

### TagFilter / hasTag(), actorHasTag(), isA()

Check if entity has a specific tag.

```python
hasTag("type:hub")          # target has tag
actorHasTag("role:it")      # actor has tag
isA("wall")                 # convenience for hasTag("type:wall")
```

### ResourceFilter / actorHas(), targetHas()

Check if entity has minimum resource amounts.

```python
actorHas({"energy": 1})             # actor has >= 1 energy
targetHas({"hp": 1})                # target has >= 1 hp
actorHasAnyOf({"gold": 1, "gem": 1})  # actor has >= 1 of either
```

### MaxDistanceFilter / maxDistance(), isNear()

Euclidean distance check (dr^2 + dc^2, no sqrt). Cannot distinguish cardinal from diagonal at distance > 1. No
line-of-sight or occlusion.

```python
maxDistance(2)                        # binary: actor within 2 of target
isNear(query("type:hub"), radius=3)  # unary: target near any hub
```

### VibeFilter / targetVibe(), actorVibe()

Check entity vibe.

```python
targetVibe("fire")
actorVibe("default")
```

### TagPrefixFilter / hasTagPrefix(), actorHasTagPrefix()

Check if entity has any tag with a given prefix.

```python
hasTagPrefix("team")           # target has any team:* tag
actorHasTagPrefix("role")      # actor has any role:* tag
```

### SharedTagPrefixFilter / sharedTagPrefix()

Check if actor and target share a tag with a given prefix. No `target` field -- always compares actor vs target.

```python
sharedTagPrefix("team")  # same team
```

### GameValueFilter

Check if a game value meets a minimum threshold. Use for dynamic conditions based on inventory, stats, or computed
values.

```python
GameValueFilter(value=inv("fuse"), min=1)
```

- `value`: Any GameValue expression
- `min`: Threshold (int or GameValue, default 0)

### PeriodicFilter

Pass at regular timestep intervals. Typically used in event filters for recurring effects.

```python
PeriodicFilter(period=5, start_on=10)  # fires at t=10, 15, 20, ...
```

- `period`: Timesteps between passes (>= 1)
- `start_on`: First timestep (defaults to `period`)
- Passes when: `(timestep - start_on) % period == 0 and timestep >= start_on`

### TargetLocEmptyFilter

Pass when the target cell has no object. Marker filter with no fields.

### TargetIsUsableFilter

Pass when target implements the Usable interface. Marker filter with no fields.

### NotFilter / isNot()

Negate any filter.

```python
isNot(actorHasTag("role:it"))  # actor does NOT have tag
```

### OrFilter / anyOf()

Pass if ANY inner filter passes.

```python
anyOf([hasTag("type:gem"), hasTag("type:gold")])
```

## Mutations (state changes)

Mutations modify grid state when a handler triggers.

### Resource: ResourceDeltaMutation / updateActor(), updateTarget()

Apply resource deltas to an entity. Positive = gain, negative = lose.

```python
updateTarget({"hp": -1, "score": 10})
updateActor({"energy": -1})
```

Does not support object removal.

### Resource: ResourceTransferMutation / withdraw(), deposit()

Transfer resources between actor and target.

```python
withdraw({"gold": 5})                          # target -> actor
withdraw({"hp": -1}, remove_when_empty=True)   # remove target when empty
deposit({"energy": 3})                         # actor -> target
```

- `remove_source_when_empty`: Remove source object from grid when inventory depleted
- In event context where actor=target (self-referencing), a self-transfer of 0 still triggers the `is_empty()` check

### Resource: ClearInventoryMutation

Clear all resources in a named limit group.

```python
ClearInventoryMutation(target=EntityTarget.TARGET, limit_name="cargo")
```

### Tag: AddTagMutation / addTag()

```python
addTag("role:it", target=EntityTarget.TARGET)
```

### Tag: RemoveTagMutation / removeTag()

```python
removeTag("role:it", target=EntityTarget.ACTOR)
```

### Tag: RemoveTagsWithPrefixMutation / removeTagPrefix()

Remove all tags matching a prefix.

```python
removeTagPrefix("role:", target=EntityTarget.TARGET)
```

### Position: RelocateMutation

Move actor to target's cell. No fields.

### Position: SwapMutation

Swap actor and target positions. No fields.

### Position: PushObjectMutation

Push target one cell along actor-to-target direction. Clamped to unit step per axis. Sets `ctx.mutation_failed = True`
if destination is off-grid or occupied. No fields.

### Spawn: SpawnObjectMutation

Spawn an object at the target's location.

```python
SpawnObjectMutation(object_type="bomb")
```

Spawns at target_location, not actor location. The agent stays in place.

### Spawn: RaycastSpawnMutation

Spawn objects along rays from target. Use for visual effects (explosion markers, beam segments).

```python
RaycastSpawnMutation(
    object_type="explosion",
    directions=["north", "south", "east", "west"],
    max_range=3,
    blocker=[hasTag("type:wall")],
)
```

- Stops at blockers, spawns only on empty cells

### Identity: ChangeVibeMutation / changeTargetVibe()

```python
changeTargetVibe("fire")
```

### Interaction: UseTargetMutation / useTarget()

Delegate to target's `on_use_handler` chain. Used in the default move handler chain.

### Interaction: AttackMutation

Combat with armor/weapon/defense mechanics. Damage = `max(weapon_power - armor_power, 0)` where powers are weighted sums
of inventory items.

```python
AttackMutation(
    weapon_resources={"sword": 10},
    armor_resources={"shield": 5},
    defense_resources={"energy": 1},
    on_success=[updateTarget({"hp": -1})],
)
```

### Stats: StatsMutation / logStat()

Set a stat to a computed value. Used for analytics and reward signals.

```python
logStatToGame("bombs_placed", delta=1)
logTargetAgentStat("damage_taken", delta=1)
```

- `target`: StatsTarget.GAME or AGENT
- `source`: Optional GameValue expression

### Game value: SetGameValueMutation

Apply delta to inventory or stat values. Exactly one of `source` (dynamic) or `delta` (static) must be set.

```python
SetGameValueMutation(value=inv("fuse"), delta=-1)
```

### Query: QueryInventoryMutation / queryDeposit(), queryWithdraw(), queryDelta()

Find objects via query, apply inventory deltas to all matches.

```python
queryDeposit(query("type:hub"), {"energy": 5})      # give energy to all hubs
queryWithdraw(query("type:mine"), {"gold": 1})       # take gold from all mines
```

- `source`: Optional EntityTarget for atomic transfer (inverse deltas applied to source)

### Query: RecomputeMaterializedQueryMutation / recomputeMaterializedQuery()

Force recomputation of MaterializedQuery membership.

```python
recomputeMaterializedQuery("network_")  # recompute all network_* tags
```

## Game Values (dynamic expressions)

Game values are composable expressions for rewards, observations, filter thresholds, and mutation sources.

| Helper                                       | Description                          |
| -------------------------------------------- | ------------------------------------ |
| `val(x)`                                     | Constant value                       |
| `inv("item")`                                | Inventory count of item              |
| `stat("name")` or `stat("scope.name")`       | Stat value (agent or game scope)     |
| `num_tagged("tag")` or `num("tag", filters)` | Count of objects matching query      |
| `QueryInventoryValue(query, item)`           | Sum of resource across query results |
| `weighted_sum([(gv, weight), ...])`          | Weighted sum of game values          |
| `GameValueRatio(num, denom)`                 | Ratio of two game values             |
| `max_value([gv, ...])`                       | Maximum of values                    |
| `min_value([gv, ...])`                       | Minimum of values                    |

## Events

Timestep-based effects targeting objects by tag query. Fire BEFORE actions and AOE each tick.

```python
EventConfig(
    name="fuse_tick",
    target_query="type:bomb",
    timesteps=periodic(start=1, period=1),
    filters=[],
    mutations=[SetGameValueMutation(value=inv("fuse"), delta=-1)],
)
```

- `target_query`: Tag name or any query
- `timesteps`: Use `periodic(start, period)` or `once(timestep)`
- `max_targets`: Optional limit (None = unlimited)
- `fallback`: Optional event name if no targets match

### Event ordering

EventScheduler uses `std::map` (alphabetical by event name), not Python dict insertion order. Events at the same
timestep fire in alphabetical name order. Name events with numeric prefixes to enforce ordering:

```python
events={
    "bomb_1_fuse_tick": ...,   # fires first
    "bomb_2_explode": ...,     # fires second
    "bomb_3_cleanup": ...,     # fires third
}
```

### ctx.target_location

In event dispatch, `ctx.target_location` is available for mutations that need the target's position (e.g.,
SpawnObjectMutation, RaycastSpawnMutation).

## Actions

Agent actions available via `ActionsConfig`.

| Action     | Handler         | Notes                                                        |
| ---------- | --------------- | ------------------------------------------------------------ |
| Noop       | `"noop"`        | Do nothing. Always enabled.                                  |
| Move       | `"move"`        | First-match handler chain. Default: 4 cardinal directions.   |
| ChangeVibe | `"change_vibe"` | Switch agent vibe. Define a minimal vibe list for your game. |
| Attack     | `"attack"`      | Triggers via move handler, not as standalone action.         |

### Move handler chain

Move uses a first-match handler chain. Can gate on vibe, resources, target cell state. Can spawn objects, relocate,
transfer resources, attack. Custom handlers override the default chain:

```python
MoveActionConfig(handlers=[
    Handler(filters=[actorVibe("fire")], mutations=[SpawnObjectMutation(object_type="bomb")]),
    Handler(filters=[], mutations=[RelocateMutation()]),  # default: walk
])
```

Custom actions beyond these four require C++ work.

## AOE (Area of Effect)

Persistent aura-like effects around objects or agents. Designed for ongoing auras, not one-shot effects.

```python
AOEConfig(
    radius=2,
    is_static=True,       # pre-computed at registration (default)
    effect_self=False,     # source not affected by own AOE
    filters=[isNot(sharedTagPrefix("team"))],
    mutations=[updateTarget({"hp": -1})],
    presence_deltas={"slow": 1},  # one-time on enter/exit
)
```

- `is_static=True` (default): Pre-computed cell set. Use for stationary sources.
- `is_static=False`: Re-evaluate each tick. Use for moving sources (agent auras).
- `apply_fixed` only evaluates agents -- GridObjects are never hit by AOE.
- Euclidean radius.

## Resource Limits

Dynamic capacity system with modifier-based scaling.

```python
ResourceLimitsConfig(
    base=5,       # capacity with no modifiers
    max=20,       # ceiling even with modifiers
    resources=["cargo"],
    modifiers={"backpack": 5},  # each backpack adds 5 capacity
)
```

Effective limit: `min(max, max(base, sum(modifier_bonus * quantity_held)))`

- `base` is the capacity with no modifiers (not a floor on the resource value)
- `max` is the absolute ceiling

## Map Builders

### AsciiMapBuilder (deterministic)

Define maps as ASCII art. Best for hand-crafted, reproducible layouts.

```python
AsciiMapBuilder.Config(
    map_data="##.##\n#...#\n##.##",
    char_to_map_name={"#": "wall", ".": "empty"},
)
```

### RandomMapBuilder (procedural)

Random placement of objects and agents within a grid.

```python
RandomMapBuilder.Config(width=20, height=20, objects={"wall": 30, "gem": 5}, agents=4, seed=42)
```

### MazePrimMapBuilder / MazeKruskalMapBuilder

Generate maze layouts using Prim's or Kruskal's algorithm.

```python
MazePrimMapBuilder.Config(width=15, height=15, start_pos=(1, 1), end_pos=(13, 13), branching=0.3)
```

### PerimeterInContextMapBuilder

Specialized builder for in-context learning scenarios.

## Episode Control

- `max_steps` is the only episode length control. No early termination primitive exists.
- Frame win conditions as reward signals, not episode terminators.
- "Pac-Man wins when all pellets are eaten" becomes "large bonus when all pellets eaten; episode runs to max_steps."

## Grid Objects & Agents

### GridObjectConfig

Base for all non-agent objects on the grid.

- `name`: Type name (used in map builders, queries)
- `tags`: Instance tags for filtering
- `handlers`: Move-triggered handler chain (when an agent walks onto the object)
- `on_use_handler`: Handler when agent uses the object
- `on_tag_remove`: Handlers triggered when a tag prefix is removed
- `inventory`: Initial resources and limits
- `aoes`: Named AOE effects
- `territory_controls`: Territory influence

### AgentConfig

Extends GridObjectConfig with agent-specific features.

- `name`: Must be `"agent"` for mettascope compatibility
- `team_id`: Team grouping (differentiate by team_id and tags, not name)
- `rewards`: Reward definitions (see Rewards)
- `on_tick`: Handler that fires every tick (agent-only; GridObjects use events)
- `on_after_use_handler`: Handler after successful use interaction

### WallConfig

Minimal wall/block. Inherits from GridObjectConfig.

## Territories

Spatial influence system for team-based area control.

```python
TerritoryConfig(
    tag_prefix="team:",
    on_enter={"score": Handler(mutations=[updateActor({"territory_score": 1})])},
    presence={"heal": Handler(filters=[sharedTagPrefix("team")], mutations=[updateTarget({"hp": 1})])},
)
```

Objects exert influence via `TerritoryControlConfig(territory="land", strength=3, decay=1)`. Observation mask: 0=no
influence, 1=friendly, 2=enemy.

## Rewards

Reward signals for RL training. Defined per-agent via `AgentReward`.

```python
AgentReward(resource="score", weight=1.0)           # inventory reward
AgentReward(game_value=stat("game.total_score"), weight=0.5)  # game value reward
```

## Observations

### ObsConfig

- `width`/`height`: Grid observation window (default 13x13)
- `token_dim`: Token embedding dimension (default 3)

### GlobalObsConfig

- `episode_completion_pct`: Include completion percentage (default True)
- `last_action`, `last_action_move`, `last_reward`: Action/reward history
- `local_position`: Directional offset tokens
- `obs`: Custom named observations as GameValue expressions

Design note: game-critical state should be stored as resources in `resource_names` (automatically observable) rather
than hidden engine state.

## Rendering (MettaScope)

### Sprites

- **Agent sprites**: `data/agents/<name>.<dir>.png` (directions: `.n`, `.s`, `.e`, `.w`)
- **Object sprites**: `data/objects/<name>.png` at 64x64
- **Vibe sprites**: `data/vibe/<name>.png` at 32x32
- Rebuild atlas after adding sprites: `cd packages/mettagrid/nim/mettascope && nim c -r tools/gen_atlas.nim`

### RenderAsset (conditional)

Match sprites by resources, tags, or both. First match wins.

```python
RenderConfig(assets={
    "bomb": [
        RenderAsset(asset="bomb_lit", resources={"fuse": 1}),  # fuse > 0: lit sprite
        RenderAsset(asset="bomb_dead"),                         # fallback: dead sprite
    ],
})
```

### HUD and Status Bars

`RenderHudConfig` for top bars, `RenderStatusBarConfig` for center-panel bars. Both keyed by resource name.

## What's NOT Possible (deliberate non-features)

- **Early episode termination.** No primitive exists. `max_steps` only. Reframe as reward signals.
- **Diagonal-only filters.** `isNear` is Euclidean. Use `RaycastQuery` with diagonal directions for directional effects.
- **Stateful Python game logic on GridObjects.** `on_tick` is agent-only. Use EventConfig for object state machines.
- **Standalone "remove object" mutation.** Use `ResourceTransferMutation` with `remove_source_when_empty=True`.
- **AOE hitting GridObjects.** `apply_fixed` only evaluates agents. Objects are never hit by AOE.
- **Custom actions without C++.** Move, noop, change_vibe, and attack are the available action types.
