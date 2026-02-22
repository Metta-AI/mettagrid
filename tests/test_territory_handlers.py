"""Integration tests for territory handler effects (on_enter, on_exit, presence).

Territory types are defined at the game level (GameConfig.territories).
Objects declare territory_controls to project influence onto nearby cells.
Per-cell ownership is determined by summing strengths (after decay) per tag,
highest total wins.

Handlers fire with actor = proxy cell object (carrying winning tag),
target = affected agent. Handlers fire on ANY owned territory; use filters
like sharedTagPrefix("team:") to restrict to friendly territory only.
"""

from mettagrid.config.filter import sharedTagPrefix
from mettagrid.config.handler_config import Handler, updateTarget
from mettagrid.config.mettagrid_config import GridObjectConfig, MettaGridConfig
from mettagrid.config.territory_config import TerritoryConfig, TerritoryControlConfig
from mettagrid.simulator import Simulation


def _make_territory_sim(
    *,
    map_data: list[str],
    char_to_map_name: dict[str, str],
    agent_team: str,
    teams: tuple[str, ...],
    resources: list[str],
    initial_inventory: dict[str, int] | None = None,
    objects: dict[str, GridObjectConfig],
    territories: dict[str, TerritoryConfig] | None = None,
) -> Simulation:
    cfg = MettaGridConfig.EmptyRoom(
        num_agents=1,
        width=len(map_data[0]),
        height=len(map_data),
        border_width=0,
    ).with_ascii_map(map_data, char_to_map_name=char_to_map_name)
    cfg.game.obs.width = len(map_data[0])
    cfg.game.obs.height = len(map_data)
    cfg.game.obs.num_tokens = 200
    cfg.game.resource_names = resources
    cfg.game.agent.tags = [f"team:{agent_team}"]
    if initial_inventory:
        cfg.game.agent.inventory.initial = initial_inventory
    cfg.game.tags = [f"team:{t}" for t in teams]
    cfg.game.territories = territories or {"team_territory": TerritoryConfig(tag_prefix="team:")}
    cfg.game.objects.update(objects)
    return Simulation(cfg)


def _territory_source(team: str, strength: int = 3) -> GridObjectConfig:
    return GridObjectConfig(
        name=f"source_{team}",
        map_name=f"source_{team}",
        tags=[f"team:{team}"],
        territory_controls=[
            TerritoryControlConfig(territory="team_territory", strength=strength),
        ],
    )


# ---------------------------------------------------------------------------
# on_enter: fires when agent steps into owned territory
# ---------------------------------------------------------------------------


def test_on_enter_fires_when_agent_moves_into_owned_territory():
    sim = _make_territory_sim(
        map_data=[
            ".......",
            "...F...",
            ".......",
            "..@....",
            ".......",
        ],
        char_to_map_name={"F": "source_cogs"},
        agent_team="cogs",
        teams=("cogs",),
        resources=["hp"],
        initial_inventory={"hp": 0},
        territories={
            "team_territory": TerritoryConfig(
                tag_prefix="team:",
                on_enter={"grant_hp": Handler(mutations=[updateTarget({"hp": 100})])},
            ),
        },
        objects={"source_cogs": _territory_source("cogs", strength=3)},
    )
    sim.agent(0).set_action("noop")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == 100

    # Second tick: still in territory, on_enter should NOT fire again.
    sim.agent(0).set_action("noop")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == 100


# ---------------------------------------------------------------------------
# on_exit: fires when agent leaves owned territory
# ---------------------------------------------------------------------------


def test_on_exit_fires_when_agent_moves_out_of_owned_territory():
    sim = _make_territory_sim(
        map_data=[
            ".........",
            "....F....",
            ".........",
            "....@....",
            ".........",
            ".........",
            ".........",
            ".........",
            ".........",
        ],
        char_to_map_name={"F": "source_cogs"},
        agent_team="cogs",
        teams=("cogs",),
        resources=["hp"],
        initial_inventory={"hp": 0},
        territories={
            "team_territory": TerritoryConfig(
                tag_prefix="team:",
                on_exit={"grant_hp": Handler(mutations=[updateTarget({"hp": 50})])},
            ),
        },
        objects={"source_cogs": _territory_source("cogs", strength=3)},
    )
    # Agent at (3,4), source at (1,4), distance=2 → in range (strength=3, decay=1).
    sim.agent(0).set_action("noop")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == 0  # on_exit hasn't fired

    # Move south twice to (5,4), distance to source = 4 > strength/decay=3 → exits territory.
    sim.agent(0).set_action("move_south")
    sim.step()
    sim.agent(0).set_action("move_south")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == 50


# ---------------------------------------------------------------------------
# presence: fires every tick while in owned territory
# ---------------------------------------------------------------------------


def test_presence_fires_every_tick_in_owned_territory():
    sim = _make_territory_sim(
        map_data=[
            ".....",
            "..F..",
            "..@..",
            ".....",
            ".....",
        ],
        char_to_map_name={"F": "source_cogs"},
        agent_team="cogs",
        teams=("cogs",),
        resources=["hp"],
        initial_inventory={"hp": 0},
        territories={
            "team_territory": TerritoryConfig(
                tag_prefix="team:",
                presence={"heal": Handler(mutations=[updateTarget({"hp": 10})])},
            ),
        },
        objects={"source_cogs": _territory_source("cogs", strength=2)},
    )
    for tick in range(1, 4):
        sim.agent(0).set_action("noop")
        sim.step()
        assert sim.agent(0).inventory.get("hp", 0) == 10 * tick


# ---------------------------------------------------------------------------
# Territory flip: counter-source takes over, exit fires
# ---------------------------------------------------------------------------


def test_on_enter_fires_in_enemy_territory_without_filter():
    """Unfiltered on_enter fires even in enemy-owned territory."""
    sim = _make_territory_sim(
        map_data=[
            ".........",
            ".........",
            ".........",
            "F..@..E..",
            ".........",
            ".........",
            ".........",
            ".........",
            ".........",
        ],
        char_to_map_name={"F": "source_cogs", "E": "source_clips"},
        agent_team="cogs",
        teams=("cogs", "clips"),
        resources=["hp"],
        initial_inventory={"hp": 0},
        territories={
            "team_territory": TerritoryConfig(
                tag_prefix="team:",
                on_enter={"grant_hp": Handler(mutations=[updateTarget({"hp": 100})])},
            ),
        },
        objects={
            "source_cogs": _territory_source("cogs", strength=3),
            "source_clips": _territory_source("clips", strength=5),
        },
    )
    # At (3,3): friendly source at (3,0) dist=3, score=0.
    # Enemy at (3,6) dist=3, strength=5, score=2. Enemy owns the cell.
    # Unfiltered on_enter fires because the cell IS owned (by enemy).
    sim.agent(0).set_action("noop")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == 100


def test_on_enter_skipped_in_enemy_territory_with_shared_tag_filter():
    """on_enter with sharedTagPrefix filter does NOT fire in enemy territory."""
    sim = _make_territory_sim(
        map_data=[
            ".........",
            ".........",
            ".........",
            "F..@..E..",
            ".........",
            ".........",
            ".........",
            ".........",
            ".........",
        ],
        char_to_map_name={"F": "source_cogs", "E": "source_clips"},
        agent_team="cogs",
        teams=("cogs", "clips"),
        resources=["hp"],
        initial_inventory={"hp": 0},
        territories={
            "team_territory": TerritoryConfig(
                tag_prefix="team:",
                on_enter={
                    "grant_hp": Handler(
                        filters=[sharedTagPrefix("team:")],
                        mutations=[updateTarget({"hp": 100})],
                    )
                },
            ),
        },
        objects={
            "source_cogs": _territory_source("cogs", strength=3),
            "source_clips": _territory_source("clips", strength=5),
        },
    )
    # Enemy owns the cell, sharedTagPrefix("team:") fails → on_enter doesn't apply.
    sim.agent(0).set_action("noop")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == 0


def test_territory_flip_fires_exit_and_enter_on_ownership_change():
    """Agent moves from friendly territory to enemy territory.
    Exit fires (old tag), then enter fires (new tag). Both carry
    the respective winning tag on the proxy cell."""
    sim = _make_territory_sim(
        map_data=[
            ".........",
            ".........",
            ".........",
            ".F.@...E.",
            ".........",
            ".........",
            ".........",
            ".........",
            ".........",
        ],
        char_to_map_name={"F": "source_cogs", "E": "source_clips"},
        agent_team="cogs",
        teams=("cogs", "clips"),
        resources=["hp"],
        initial_inventory={"hp": 0},
        territories={
            "team_territory": TerritoryConfig(
                tag_prefix="team:",
                on_enter={
                    "grant_hp": Handler(
                        filters=[sharedTagPrefix("team:")],
                        mutations=[updateTarget({"hp": 100})],
                    )
                },
                on_exit={
                    "drain_hp": Handler(
                        filters=[sharedTagPrefix("team:")],
                        mutations=[updateTarget({"hp": -50})],
                    )
                },
            ),
        },
        objects={
            "source_cogs": _territory_source("cogs", strength=3),
            "source_clips": _territory_source("clips", strength=3),
        },
    )
    # Agent at (3,3), friendly at (3,1) dist=2, enemy at (3,7) dist=4.
    # Friendly: max(0, 3-2)=1. Enemy: max(0, 3-4)=0. Friendly wins → on_enter fires.
    sim.agent(0).set_action("noop")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == 100

    # Move east 2 cells to (3,5). Friendly dist=4, score=0. Enemy dist=2, score=1.
    # Territory flips: exit fires with old (friendly) tag → sharedTagPrefix passes → -50.
    # Then enter fires with new (enemy) tag → sharedTagPrefix fails → no effect.
    sim.agent(0).set_action("move_east")
    sim.step()
    sim.agent(0).set_action("move_east")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == 50


# ---------------------------------------------------------------------------
# Filter interaction: on_enter with sharedTagPrefix filter
# ---------------------------------------------------------------------------


def test_on_enter_with_shared_tag_filter():
    """on_enter handler has a sharedTagPrefix filter — fires because the proxy
    cell carries the winning tag (same team prefix as the agent)."""
    sim = _make_territory_sim(
        map_data=[
            ".....",
            "..F..",
            "..@..",
            ".....",
            ".....",
        ],
        char_to_map_name={"F": "source_cogs"},
        agent_team="cogs",
        teams=("cogs",),
        resources=["hp"],
        initial_inventory={"hp": 0},
        territories={
            "team_territory": TerritoryConfig(
                tag_prefix="team:",
                on_enter={
                    "grant_hp": Handler(
                        filters=[sharedTagPrefix("team:")],
                        mutations=[updateTarget({"hp": 77})],
                    )
                },
            ),
        },
        objects={"source_cogs": _territory_source("cogs", strength=2)},
    )
    sim.agent(0).set_action("noop")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == 77


# ---------------------------------------------------------------------------
# Dynamic territory changes: tag mutations flip ownership
# ---------------------------------------------------------------------------


def _tag_id(cfg, tag_name: str) -> int:
    id_map = cfg.game.id_map()
    names = id_map.tag_names()
    return {n: i for i, n in enumerate(names)}[tag_name]


def _find_obj(sim, type_name: str) -> dict:
    for _id, obj in sim.grid_objects().items():
        if obj["type_name"] == type_name:
            return obj
    raise RuntimeError(f"No object of type '{type_name}' found")


def test_source_tag_change_flips_territory():
    """Source switches team tag → territory ownership flips.

    Agent (team:cogs) is in friendly territory. Source loses team:cogs and
    gains team:clips. Exit fires with old friendly tag (sharedTagPrefix passes),
    enter fires with new enemy tag (sharedTagPrefix fails). Presence healing
    stops because filter no longer matches.
    """
    cfg = MettaGridConfig.EmptyRoom(num_agents=1, width=5, height=5, border_width=0).with_ascii_map(
        [".....", "..F..", "..@..", ".....", "....."],
        char_to_map_name={"F": "source_cogs"},
    )
    cfg.game.obs.width = 5
    cfg.game.obs.height = 5
    cfg.game.obs.num_tokens = 200
    cfg.game.resource_names = ["hp"]
    cfg.game.agent.tags = ["team:cogs"]
    cfg.game.agent.inventory.initial = {"hp": 500}
    cfg.game.tags = ["team:cogs", "team:clips"]
    cfg.game.territories = {
        "team_territory": TerritoryConfig(
            tag_prefix="team:",
            on_exit={
                "drain_hp": Handler(
                    filters=[sharedTagPrefix("team:")],
                    mutations=[updateTarget({"hp": -50})],
                )
            },
            presence={
                "heal": Handler(
                    filters=[sharedTagPrefix("team:")],
                    mutations=[updateTarget({"hp": 10})],
                )
            },
        ),
    }
    cfg.game.objects["source_cogs"] = _territory_source("cogs", strength=3)
    sim = Simulation(cfg)

    # Tick 1: agent in friendly territory → presence heals +10.
    sim.agent(0).set_action("noop")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == 510

    # Tick 2: still friendly → +10 again.
    sim.agent(0).set_action("noop")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == 520

    # Flip the source from team:cogs to team:clips between ticks.
    source = _find_obj(sim, "source_cogs")
    cogs_id = _tag_id(cfg, "team:cogs")
    clips_id = _tag_id(cfg, "team:clips")
    source["remove_tag"](cogs_id)
    source["add_tag"](clips_id)

    # Tick 3: territory now enemy-owned.
    # on_exit fires with old (cogs) tag → sharedTagPrefix passes → -50.
    # presence fires with clips tag → sharedTagPrefix fails → no heal.
    sim.agent(0).set_action("noop")
    sim.step()
    hp_after_flip = sim.agent(0).inventory.get("hp", 0)
    assert hp_after_flip == 520 - 50

    # Tick 4: agent still in enemy territory, presence filter fails → no heal.
    sim.agent(0).set_action("noop")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == hp_after_flip


def test_stronger_source_appearing_flips_territory():
    """A neutral source gains a team tag and overpowers the current owner.

    Agent (team:cogs) is in friendly cogs territory. A stronger source nearby
    has no team tag initially. When it gains team:clips, it overpowers cogs
    and territory flips → exit fires, presence stops.
    """
    cfg = MettaGridConfig.EmptyRoom(num_agents=1, width=7, height=5, border_width=0).with_ascii_map(
        [".......", "..F.N..", "...@...", ".......", "......."],
        char_to_map_name={"F": "source_cogs", "N": "strong_neutral"},
    )
    cfg.game.obs.width = 7
    cfg.game.obs.height = 5
    cfg.game.obs.num_tokens = 200
    cfg.game.resource_names = ["hp"]
    cfg.game.agent.tags = ["team:cogs"]
    cfg.game.agent.inventory.initial = {"hp": 500}
    cfg.game.tags = ["team:cogs", "team:clips"]
    cfg.game.territories = {
        "team_territory": TerritoryConfig(
            tag_prefix="team:",
            on_exit={
                "drain": Handler(
                    filters=[sharedTagPrefix("team:")],
                    mutations=[updateTarget({"hp": -100})],
                )
            },
            presence={
                "heal": Handler(
                    filters=[sharedTagPrefix("team:")],
                    mutations=[updateTarget({"hp": 10})],
                )
            },
        ),
    }
    cfg.game.objects["source_cogs"] = _territory_source("cogs", strength=3)
    cfg.game.objects["strong_neutral"] = GridObjectConfig(
        name="strong_neutral",
        map_name="strong_neutral",
        tags=[],
        territory_controls=[
            TerritoryControlConfig(territory="team_territory", strength=5),
        ],
    )
    sim = Simulation(cfg)

    # Tick 1: only cogs source active → agent in friendly territory → +10.
    sim.agent(0).set_action("noop")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == 510

    # Give the strong source a team:clips tag.
    neutral = _find_obj(sim, "strong_neutral")
    clips_id = _tag_id(cfg, "team:clips")
    neutral["add_tag"](clips_id)

    # Tick 2: strong_neutral (strength=5) overpowers cogs source (strength=3).
    # Exit fires with old cogs tag → sharedTagPrefix passes → -100.
    # Presence with clips tag → sharedTagPrefix fails → no heal.
    sim.agent(0).set_action("noop")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == 510 - 100


def test_agent_tag_change_affects_presence_filter():
    """Agent switches team tag → presence filter result changes.

    Territory ownership does NOT change (source still cogs), but the agent
    no longer shares the winning tag. Presence handler with sharedTagPrefix
    stops firing. No exit/enter fires because the cell's winning tag didn't change.
    """
    cfg = MettaGridConfig.EmptyRoom(num_agents=1, width=5, height=5, border_width=0).with_ascii_map(
        [".....", "..F..", "..@..", ".....", "....."],
        char_to_map_name={"F": "source_cogs"},
    )
    cfg.game.obs.width = 5
    cfg.game.obs.height = 5
    cfg.game.obs.num_tokens = 200
    cfg.game.resource_names = ["hp"]
    cfg.game.agent.tags = ["team:cogs"]
    cfg.game.agent.inventory.initial = {"hp": 0}
    cfg.game.tags = ["team:cogs", "team:clips"]
    cfg.game.territories = {
        "team_territory": TerritoryConfig(
            tag_prefix="team:",
            on_exit={
                "drain": Handler(
                    filters=[sharedTagPrefix("team:")],
                    mutations=[updateTarget({"hp": -1000})],
                )
            },
            presence={
                "heal": Handler(
                    filters=[sharedTagPrefix("team:")],
                    mutations=[updateTarget({"hp": 10})],
                )
            },
        ),
    }
    cfg.game.objects["source_cogs"] = _territory_source("cogs", strength=3)
    sim = Simulation(cfg)

    # Tick 1: friendly → presence heals +10.
    sim.agent(0).set_action("noop")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == 10

    # Switch agent from team:cogs to team:clips.
    agent_obj = _find_obj(sim, "agent")
    cogs_id = _tag_id(cfg, "team:cogs")
    clips_id = _tag_id(cfg, "team:clips")
    agent_obj["remove_tag"](cogs_id)
    agent_obj["add_tag"](clips_id)

    # Tick 2: territory still cogs-owned (source hasn't changed).
    # No exit/enter fires (winning tag at cell is unchanged).
    # Presence fires but sharedTagPrefix("team:") fails (agent=clips, cell=cogs).
    # hp stays at 10 — no drain (exit didn't fire), no heal.
    sim.agent(0).set_action("noop")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == 10

    # Tick 3: same state, still no healing.
    sim.agent(0).set_action("noop")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == 10


def test_agent_territory_source_follows_movement() -> None:
    """Agent with territory_controls projects influence that moves with it.

    Agent at (1,1) with strength=2 (effective radius=2). Presence handler
    heals +10/tick in friendly territory. The agent moves east 3 cells to
    (1,4), well beyond its spawn radius. Because influence follows the
    agent, it stays at distance 0 from itself and keeps getting healed.
    """
    cfg = MettaGridConfig.EmptyRoom(
        num_agents=1,
        width=7,
        height=3,
        border_width=0,
    ).with_ascii_map([".......", ".@.....", "......."], char_to_map_name={})
    cfg.game.obs.width = 7
    cfg.game.obs.height = 3
    cfg.game.obs.num_tokens = 200
    cfg.game.resource_names = ["hp"]
    cfg.game.agent.tags = ["team:cogs"]
    cfg.game.agent.inventory.initial = {"hp": 0}
    cfg.game.agent.territory_controls = [
        TerritoryControlConfig(territory="team_territory", strength=2),
    ]
    cfg.game.tags = ["team:cogs"]
    cfg.game.territories = {
        "team_territory": TerritoryConfig(
            tag_prefix="team:",
            presence={
                "heal": Handler(
                    filters=[sharedTagPrefix("team:")],
                    mutations=[updateTarget({"hp": 10})],
                )
            },
        ),
    }
    sim = Simulation(cfg)

    # Tick 1: agent at (1,1), dist 0 from itself → friendly territory → healed.
    sim.agent(0).set_action("noop")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == 10

    # Move east 3 times: (1,1) → (1,4). Spawn point is now outside radius 2.
    for _ in range(3):
        sim.agent(0).set_action("move_east")
        sim.step()

    # Noop tick at (1,4). If influence followed, agent is still at dist 0
    # from itself → healed. If stuck at spawn, agent is at dist 3 > radius 2
    # → no territory → no heal.
    hp_before = sim.agent(0).inventory.get("hp", 0)
    sim.agent(0).set_action("noop")
    sim.step()
    assert sim.agent(0).inventory.get("hp", 0) == hp_before + 10
