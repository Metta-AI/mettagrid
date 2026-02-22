# MettaGrid Territory System - Technical Manual

This document explains the territory system: how spatial influence zones are defined, computed, observed, and how they
drive gameplay effects through handlers.

## Overview

Territory is a **game-level** concept where objects project influence onto nearby grid cells. For each cell, the system
aggregates influence from all contributing objects, grouped by tag. The tag with the highest total influence wins that
cell. Territory enables:

- **Observation masks** — agents observe whether each nearby tile is friendly, enemy, or neutral.
- **Handler effects** — `on_enter`, `on_exit`, and `presence` handlers fire as agents move through territory.

Territory types are defined on `GameConfig.territories`. Objects declare which territory types they influence via
`GridObjectConfig.territory_controls`.

## Configuration

### Game-Level: TerritoryConfig

Defined in `GameConfig.territories` as a `dict[str, TerritoryConfig]`. Each entry names a territory type (e.g.
`"team_territory"`) and configures:

| Field        | Type                 | Description                                                     |
| ------------ | -------------------- | --------------------------------------------------------------- |
| `tag_prefix` | `str`                | Tag prefix for team identification (e.g. `"team:"`).            |
| `on_enter`   | `dict[str, Handler]` | Handlers fired once when an agent enters owned territory.       |
| `on_exit`    | `dict[str, Handler]` | Handlers fired once when an agent leaves owned territory.       |
| `presence`   | `dict[str, Handler]` | Handlers fired every tick while an agent is in owned territory. |

Example:

```python
GameConfig(
    territories={
        "team_territory": TerritoryConfig(
            tag_prefix="team:",
            presence={
                "heal": Handler(
                    filters=[sharedTagPrefix("team:")],
                    mutations=[updateTarget({"energy": 100, "hp": 100})],
                ),
                "influence": Handler(
                    filters=[sharedTagPrefix("team:")],
                    mutations=[updateTarget({"influence": 1})],
                ),
            },
        ),
    },
    ...
)
```

### Object-Level: TerritoryControlConfig

Defined in `GridObjectConfig.territory_controls` as a `list[TerritoryControlConfig]`. Each entry declares that the
object projects influence onto a territory type:

| Field       | Type  | Default | Description                                                   |
| ----------- | ----- | ------- | ------------------------------------------------------------- |
| `territory` | `str` | —       | Key into `GameConfig.territories`.                            |
| `strength`  | `int` | `1`     | Base influence at distance 0.                                 |
| `decay`     | `int` | `1`     | Strength lost per unit of Euclidean distance from the object. |

The object must carry a tag matching the territory's `tag_prefix` to participate. For example, a hub with
`tags=["team:cogs"]` and `territory_controls=[TerritoryControlConfig(territory="team_territory", strength=10)]` projects
influence for the `"team:cogs"` side of `"team_territory"`.

## Influence Model

Influence at distance `d` from a source with strength `s` and decay `k`:

```
influence(s, k, d) = max(0, s - k * d)
```

Where `d` is the Euclidean distance from the source to the cell center. The **effective radius** — the farthest cell
that receives any influence — is `s / k`.

The implementation uses 1024x integer scaling internally for sub-cell precision without floating point.

### Cell Ownership

For each cell and each territory type:

1. Collect all `TerritoryControlConfig` sources whose effective radius covers this cell.
2. For each source, find its tag matching the territory's `tag_prefix` (e.g. `"team:cogs"`).
3. Sum influence scores per tag across all sources.
4. The tag with the highest total score wins. **Ties resolve to neutral** (no owner).

## Observation Mask

When `ObsConfig.aoe_mask=True`, the territory system emits a per-tile token in each agent's observation:

| Value | Meaning                                      |
| ----- | -------------------------------------------- |
| `0`   | Neutral (no influence, tie, or out of range) |
| `1`   | Friendly (observer shares the winning tag)   |
| `2`   | Enemy (observer does not share winning tag)  |

If multiple territory types exist, the first non-neutral result is reported.

## Handler Effects

Territory handlers fire with `actor` = a proxy cell object (carrying the winning tag of the cell) and `target` = the
affected agent. **Handlers fire on any owned territory**, regardless of which team owns it. Use filters like
`sharedTagPrefix("team:")` to restrict effects to friendly territory, or invert with `isNot(sharedTagPrefix(...))` for
enemy-only effects.

### on_enter

Fired **once** when a cell transitions from neutral to owned, or when ownership flips to a different tag. Triggers:

- Agent moves into owned territory from neutral.
- A new source is registered that claims a previously neutral cell.
- Ownership flips from one tag to another (exit fires for old tag, then enter for new tag).

### on_exit

Fired **once** when a cell transitions from owned to neutral, or when ownership flips. The proxy cell carries the
**previous** winning tag so filters can identify which team the agent is leaving.

### presence

Fired **every tick** while the agent is in any owned territory. Fires once per territory type per tick, regardless of
how many sources contribute to the cell.

### Friendly-Only Example

```python
TerritoryConfig(
    tag_prefix="team:",
    presence={
        "heal": Handler(
            filters=[sharedTagPrefix("team:")],
            mutations=[updateTarget({"energy": 100, "hp": 100})],
        ),
    },
)
```

The `sharedTagPrefix("team:")` filter compares the agent's team tag against the proxy cell's winning tag. It passes only
when the agent shares the cell's winning tag (i.e., friendly territory).

## Relationship to AOE

Territory and AOE are separate systems:

| Concern         | Territory                            | AOE                                   |
| --------------- | ------------------------------------ | ------------------------------------- |
| Defined on      | `GameConfig.territories`             | `GridObjectConfig.aoes`               |
| Spatial model   | Influence aggregated per cell        | Per-source radius check               |
| Team resolution | Tag-based competition (highest wins) | Filter-based (e.g. `sharedTagPrefix`) |
| Effects         | Handlers on `TerritoryConfig`        | Mutations/presence on `AOEConfig`     |
| Observation     | `aoe_mask` observation tokens        | No observation output                 |

Objects can participate in both systems simultaneously. For example, an object might project territory influence _and_
have an independent AOE with different filters/mutations.

## Runtime: TerritoryTracker (C++)

`TerritoryTracker` is constructed with grid dimensions and the game-level `TerritoryConfig` list. It:

1. **Pre-registers sources** — `register_source(object, control)` writes the source into all cells within its effective
   radius.
2. **Computes ownership per tick** — for each agent, `apply_effects()` determines cell ownership per territory type and
   fires enter/exit/presence handlers.
3. **Emits observations** — `compute_observability_at()` returns friendly/enemy/neutral per tile for the observation
   encoder.

Source registration is spatial: changing a source's tags or removing a source triggers re-evaluation of ownership at
affected cells on the next tick.
