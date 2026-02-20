"""Tests for object map_name keying in C++ config conversion.

Verifies that convert_to_cpp_game_config stores objects under their map_name
(not the Python dict key), so that AsciiMapBuilder cell names resolve correctly
in C++ initialization.
"""

from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    CollectiveConfig,
    GameConfig,
    GridObjectConfig,
    InventoryConfig,
    MettaGridConfig,
    NoopActionConfig,
    ObsConfig,
    WallConfig,
)
from mettagrid.map_builder.ascii import AsciiMapBuilder
from mettagrid.simulator import Simulation


def _minimal_game_config(**overrides) -> GameConfig:
    defaults = dict(
        num_agents=1,
        obs=ObsConfig(width=5, height=5, num_tokens=100),
        max_steps=10,
        actions=ActionsConfig(noop=NoopActionConfig()),
        resource_names=[],
    )
    defaults.update(overrides)
    return GameConfig(**defaults)


def _sim(game_config: GameConfig) -> Simulation:
    return Simulation(MettaGridConfig(game=game_config))


class TestMapNameKeying:
    """Objects keyed by map_name spawn correctly via AsciiMapBuilder."""

    def test_dict_key_equals_map_name(self):
        """Standard case: dict key matches map_name, object spawns normally."""
        cfg = _minimal_game_config(
            objects={"wall": WallConfig()},
            map_builder=AsciiMapBuilder.Config(
                map_data=[
                    ["#", ".", "#"],
                    [".", "@", "."],
                    [".", ".", "."],
                ],
                char_to_map_name={},
            ),
        )
        sim = _sim(cfg)
        walls = [o for o in sim.grid_objects().values() if o.get("type_name") == "wall"]
        assert len(walls) == 2

    def test_dict_key_differs_from_map_name(self):
        """When dict key != map_name, the map_name is what the map builder uses."""
        cfg = _minimal_game_config(
            objects={
                "cogs_hub_key": GridObjectConfig(name="hub", map_name="c:hub"),
            },
            map_builder=AsciiMapBuilder.Config(
                map_data=[
                    [".", "H", "."],
                    [".", "@", "."],
                    [".", ".", "."],
                ],
                char_to_map_name={"H": "c:hub"},
            ),
        )
        sim = _sim(cfg)
        hubs = [o for o in sim.grid_objects().values() if o.get("type_name") == "hub"]
        assert len(hubs) == 1

    def test_same_type_different_map_names(self):
        """Multiple objects with the same name but distinct map_names spawn separately."""
        cfg = _minimal_game_config(
            resource_names=["gold"],
            objects={
                "cogs_hub": GridObjectConfig(
                    name="hub",
                    map_name="c:hub",
                    tags=["team:cogs"],
                    inventory=InventoryConfig(initial={"gold": 10}),
                ),
                "clips_hub": GridObjectConfig(
                    name="hub",
                    map_name="clips:hub",
                    tags=["team:clips"],
                    inventory=InventoryConfig(initial={"gold": 50}),
                ),
            },
            tags=["team:cogs", "team:clips"],
            map_builder=AsciiMapBuilder.Config(
                map_data=[
                    [".", "H", ".", "J", "."],
                    [".", ".", "@", ".", "."],
                    [".", ".", ".", ".", "."],
                ],
                char_to_map_name={"H": "c:hub", "J": "clips:hub"},
            ),
        )
        sim = _sim(cfg)
        hubs = [o for o in sim.grid_objects().values() if o.get("type_name") == "hub"]
        assert len(hubs) == 2

    def test_map_name_defaults_to_name(self):
        """When map_name is omitted, it defaults to name; dict key is irrelevant."""
        cfg = _minimal_game_config(
            objects={
                "my_wall_key": WallConfig(name="wall"),
            },
            map_builder=AsciiMapBuilder.Config(
                map_data=[
                    ["#", "#", "#"],
                    [".", "@", "."],
                    [".", ".", "."],
                ],
                char_to_map_name={},
            ),
        )
        sim = _sim(cfg)
        walls = [o for o in sim.grid_objects().values() if o.get("type_name") == "wall"]
        assert len(walls) == 3

    def test_wall_with_custom_map_name(self):
        """WallConfig with a custom map_name='C' can be placed via that character."""
        cfg = _minimal_game_config(
            objects={
                "wall": WallConfig(),
                "clips_wall_key": WallConfig(name="wall", map_name="C"),
            },
            map_builder=AsciiMapBuilder.Config(
                map_data=[
                    ["#", "C", "#"],
                    [".", "@", "."],
                    [".", ".", "."],
                ],
                char_to_map_name={"C": "C"},
            ),
        )
        sim = _sim(cfg)
        walls = [o for o in sim.grid_objects().values() if o.get("type_name") == "wall"]
        assert len(walls) == 3

    def test_collective_objects_with_map_names(self):
        """Objects belonging to different collectives use map_name for lookup."""
        cfg = _minimal_game_config(
            objects={
                "cogs_hub": GridObjectConfig(
                    name="hub",
                    map_name="c:hub",
                    tags=["team:cogs"],
                    collective="cogs",
                ),
                "clips_hub": GridObjectConfig(
                    name="hub",
                    map_name="clips:hub",
                    tags=["team:clips"],
                    collective="clips",
                ),
            },
            collectives={
                "cogs": CollectiveConfig(),
                "clips": CollectiveConfig(),
            },
            tags=["team:cogs", "team:clips"],
            map_builder=AsciiMapBuilder.Config(
                map_data=[
                    [".", "H", ".", "J", "."],
                    [".", ".", "@", ".", "."],
                    [".", ".", ".", ".", "."],
                ],
                char_to_map_name={"H": "c:hub", "J": "clips:hub"},
            ),
        )
        sim = _sim(cfg)
        hubs = [o for o in sim.grid_objects().values() if o.get("type_name") == "hub"]
        assert len(hubs) == 2

        collective_ids = {o.get("collective_id") for o in hubs}
        assert len(collective_ids) == 2, "Hubs should belong to different collectives"

    def test_objects_with_different_inventories(self):
        """Same-typed objects with different map_names have their own inventory configs."""
        cfg = _minimal_game_config(
            resource_names=["gold"],
            objects={
                "rich_chest": GridObjectConfig(
                    name="chest",
                    map_name="R",
                    inventory=InventoryConfig(initial={"gold": 100}),
                ),
                "poor_chest": GridObjectConfig(
                    name="chest",
                    map_name="P",
                    inventory=InventoryConfig(initial={"gold": 1}),
                ),
            },
            map_builder=AsciiMapBuilder.Config(
                map_data=[
                    ["R", ".", "P"],
                    [".", "@", "."],
                    [".", ".", "."],
                ],
                char_to_map_name={"R": "R", "P": "P"},
            ),
        )
        sim = _sim(cfg)
        chests = [o for o in sim.grid_objects().values() if o.get("type_name") == "chest"]
        assert len(chests) == 2

    def test_three_variants_same_type(self):
        """Three objects sharing a name, each with a unique map_name, all spawn."""
        cfg = _minimal_game_config(
            objects={
                "station_a": GridObjectConfig(name="station", map_name="s:alpha"),
                "station_b": GridObjectConfig(name="station", map_name="s:beta"),
                "station_c": GridObjectConfig(name="station", map_name="s:gamma"),
            },
            map_builder=AsciiMapBuilder.Config(
                map_data=[
                    ["A", "B", "G"],
                    [".", "@", "."],
                    [".", ".", "."],
                ],
                char_to_map_name={"A": "s:alpha", "B": "s:beta", "G": "s:gamma"},
            ),
        )
        sim = _sim(cfg)
        stations = [o for o in sim.grid_objects().values() if o.get("type_name") == "station"]
        assert len(stations) == 3

    def test_three_junctions_different_properties(self):
        """Three junctions (same type) with different map_names, tags, and inventories.

        Verifies that each spawned object has type_name 'junction' but carries
        distinct per-variant inventory and collective assignment.
        """
        resources = ["gold", "silver", "gems"]
        cfg = _minimal_game_config(
            resource_names=resources,
            objects={
                "junction_cogs": GridObjectConfig(
                    name="junction",
                    map_name="j1",
                    tags=["team:cogs"],
                    collective="cogs",
                    inventory=InventoryConfig(initial={"gold": 100}),
                ),
                "junction_clips": GridObjectConfig(
                    name="junction",
                    map_name="j2",
                    tags=["team:clips"],
                    collective="clips",
                    inventory=InventoryConfig(initial={"silver": 200}),
                ),
                "junction_neutral": GridObjectConfig(
                    name="junction",
                    map_name="j3",
                    inventory=InventoryConfig(initial={"gems": 50}),
                ),
            },
            collectives={
                "cogs": CollectiveConfig(),
                "clips": CollectiveConfig(),
            },
            tags=["team:cogs", "team:clips"],
            map_builder=AsciiMapBuilder.Config(
                map_data=[
                    ["1", "2", "3"],
                    [".", "@", "."],
                    [".", ".", "."],
                ],
                char_to_map_name={"1": "j1", "2": "j2", "3": "j3"},
            ),
        )
        sim = _sim(cfg)
        objs = sim.grid_objects()
        junctions = [o for o in objs.values() if o.get("type_name") == "junction"]
        assert len(junctions) == 3

        gold_id = resources.index("gold")
        silver_id = resources.index("silver")
        gems_id = resources.index("gems")

        by_col = {j["c"]: j for j in junctions}

        j1 = by_col[0]
        assert j1["type_name"] == "junction"
        assert j1["inventory"][gold_id] == 100
        assert j1["inventory"].get(silver_id, 0) == 0
        assert j1["inventory"].get(gems_id, 0) == 0
        assert j1.get("collective_name") == "cogs"

        j2 = by_col[1]
        assert j2["type_name"] == "junction"
        assert j2["inventory"].get(gold_id, 0) == 0
        assert j2["inventory"][silver_id] == 200
        assert j2["inventory"].get(gems_id, 0) == 0
        assert j2.get("collective_name") == "clips"

        j3 = by_col[2]
        assert j3["type_name"] == "junction"
        assert j3["inventory"].get(gold_id, 0) == 0
        assert j3["inventory"].get(silver_id, 0) == 0
        assert j3["inventory"][gems_id] == 50
        assert j3.get("collective_name") is None
