# Making a CoGame

This guide is for people who want to build a new game on top of CoGames and MettaGrid. It covers the simulation primitives, how to define game objects and rules, how to wrap everything into a playable mission, and how to write evals. For a complete worked example of a cooperative-competitive game built this way, see `cogsguard/`.

---

## What MettaGrid gives you

MettaGrid is the simulation engine. It's written in C++ with a Python config layer, and runs fast enough to train on — thousands of environments in parallel, millions of timesteps.

You describe your game entirely in Python config objects. MettaGrid handles the physics: moving agents, resolving actions, computing observations, tracking inventories. You get back a standard Gymnasium-compatible environment.

**What you define:**
- The **map** — size, layout, object placement (procedural generators or ASCII files)
- The **objects** — anything on the grid: walls, resource nodes, crafting stations, territory markers, whatever your game needs
- The **agents** — what they can carry, what actions they can take, what they see
- The **rewards** — what agents get credit for
- The **events** — things that happen at specific timesteps

**What agents see** is a token-based local window. By default, each agent observes an 11×11 grid around itself as a list of up to 300 tokens (each token has 3 values). Every visible object — agents, walls, resources, buildings — becomes a token describing its type, inventory, and tags. Agents also get a small set of global tokens: episode completion percentage, last action taken, last reward received. The window size and token budget are configurable in `ObsConfig`.

---

## The CoGames framework

CoGames adds a thin layer on top of MettaGrid for defining missions, maps, and composable modifiers.

**`CoGameMission`** is the base class for a playable mission. Subclass it and implement `make_env()` to produce a `MettaGridConfig`. It holds the site, agent count, max steps, and a list of variants.

**`CoGameSite`** defines the map layout — a procedural generator or a fixed ASCII file — along with agent count bounds.

**`CoGameMissionVariant`** is a composable modifier. It has two hooks:
- `modify_mission(mission)` — called at construction time, modifies mission-level config in place
- `modify_env(mission, env)` — called in `make_env()`, modifies the produced `MettaGridConfig` in place

Variants are applied in order. Stack them to combine pressures: a difficulty variant, a reward-shaping variant, and a map variant are all independent and compose cleanly.

---

## Defining your game

### Objects and handlers

Everything on the grid is a `GridObjectConfig`. Objects have an inventory (what resources they hold) and handlers (what happens when an agent moves into their cell).

```python
# A resource node agents can mine
ore_vein = GridObjectConfig(
    name="ore_vein",
    inventory=InventoryConfig(initial={"ore": 100}),
    on_use_handler=Handler(
        name="extract",
        mutations=[withdraw({"ore": 5})]  # transfers 5 ore from vein → agent
    )
)

# A station that converts ore into ingots
refinery = GridObjectConfig(
    name="refinery",
    on_use_handler=Handler(
        name="smelt",
        filters=[actorHas({"ore": 5})],
        mutations=[updateActor({"ore": -5, "ingot": 1})]
    )
)
```

`withdraw` takes resources from the object and gives them to the agent. `deposit` does the reverse. `updateActor`/`updateTarget` apply signed deltas directly — useful for crafting and conversion.

For single interactions, use a bare `Handler`. When an object needs multiple conditional interactions, wrap them in `firstMatch([...])` — the first handler whose filters all pass fires, and the rest are skipped. This lets you define conditional interactions — a handler that requires a key, with a weaker fallback for agents without one.

**Area-of-effect handlers** fire every timestep on all agents within a radius, without any agent action required — useful for territory effects, passive damage, healing zones.

### Agents and rewards

```python
agent_cfg = AgentConfig(
    inventory=InventoryConfig(
        default_limit=20,
        initial={"ore": 0, "ingot": 0, "hp": 10}
    ),
    rewards={"ingot": inventoryReward("ingot", weight=1.0)},
)
```

Shape behavior by choosing what resources to reward and at what weight.

### Events

Events fire mutations on matching objects at specific timesteps:

```python
events = {
    "replenish": EventConfig(
        target_query=query(typeTag("ore_vein")),
        timesteps=periodic(start=500, period=500),  # fires at 500, 1000, 1500...
        mutations=[updateTarget({"ore": 50})],      # refill all ore veins
    ),
}
```

Use `once(timestep)` for a one-shot event, `periodic(start, period)` for repeating ones. Events are good for resource replenishment, scarcity shocks, and environmental pressure that changes over an episode.

### Maps

**Procedural** maps are generated fresh each episode — good for training generalization. `BaseHub.Config` gives you a hub-and-spoke layout with configurable spawn counts, junction objects, and corner bundles.

**Fixed ASCII** maps give the same layout every run — essential for reproducible evals. Define a `.map` file and load it with `MapBuilderConfig.from_uri(...)`.

---

## Wrapping it as a mission

Assemble the pieces into a `MettaGridConfig` inside `make_env()`. Use `self.max_steps`, `self.num_cogs`, and `self.site.map_builder` — not hardcoded literals — so that variants and mission-level overrides actually take effect. Your `make_env()` is also responsible for calling `modify_env` on all variants.

```python
class OreMineMission(CoGameMission):
    name: str = "ore_mine"
    description: str = "Extract ore, smelt ingots."
    site: CoGameSite = SmallMine
    num_cogs: int = 4

    def make_env(self) -> MettaGridConfig:
        env = MettaGridConfig(
            game=GameConfig(
                num_agents=self.num_cogs,
                max_steps=self.max_steps,
                resource_names=["ore", "ingot", "hp"],
                objects={"wall": WallConfig(), "ore_vein": ore_vein, "refinery": refinery},
                actions=ActionsConfig(move=MoveActionConfig(), noop=NoopActionConfig()),
                agent=agent_cfg,
                events=events,
                map_builder=self.site.map_builder,
            )
        )
        env = env.model_copy(deep=True)
        env.label = self.full_name()
        for variant in self.variants:
            variant.modify_env(self, env)
        return env
```

```bash
cogames play --mission my_module.OreMineMission --cogs 4
```

---

## Variants

Variants keep "what the game is" separate from "how hard it is" and "what gets rewarded." Define them as Pydantic classes:

```python
class ScarcityVariant(CoGameMissionVariant):
    name: str = "scarcity"
    description: str = "Ore veins start nearly empty."

    def modify_env(self, mission: CoGameMission, env: MettaGridConfig) -> None:
        for obj in env.game.objects.values():
            if obj.name == "ore_vein":
                obj.inventory.initial["ore"] = 10  # default is 100

class ShortRunVariant(CoGameMissionVariant):
    name: str = "short_run"
    description: str = "Half the episode length."

    def modify_mission(self, mission: CoGameMission) -> None:
        mission.max_steps = mission.max_steps // 2
```

Apply them at definition time:

```python
HardOreMineMission = OreMineMission(
    name="ore_mine_hard",
    description="Scarce ore, short clock.",
    site=SmallMine,
    num_cogs=4,
    variants=[ScarcityVariant(), ShortRunVariant()],
)
```

---

## Training

```bash
cogames tutorial train \
    --mission my_module.OreMineMission \
    --steps 2000000
```

CoGames uses [PufferLib](https://github.com/PufferAI/PufferLib) for training — PPO with parallel vectorized environments. The trained checkpoint loads back for play or eval:

```bash
cogames play --mission my_module.OreMineMission --policy file://./checkpoints/latest.pt
```

Before committing training time, run `cogames play --mission my_module.OreMineMission` to verify the game interactively — check that maps generate correctly, handlers fire, and rewards accumulate as expected.

---

## Evals

**Evals are missions too** — the same class, just with a fixed map and a focused objective. Write one for each behavior you care about: navigation, resource transfer, coordination. A fixed map means the same result every run; a regression shows up immediately.

For broader testing, compose variants onto a procedural mission. A policy that passes a fixed diagnostic might collapse when ore is scarce or buildings are in unfamiliar positions. A good eval suite has both: diagnostics to catch regressions fast, integrated evals to confirm generalization.

```bash
cogames play --mission my_module.NavigationEval --cogs 1
```
