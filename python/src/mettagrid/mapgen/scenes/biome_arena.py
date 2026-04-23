"""Composite arena scenes: base biome + random biomes + random dungeons + buildings + compound(s)."""

from __future__ import annotations

from typing import Any

import numpy as np
from pydantic import Field

from mettagrid.map_builder.map_builder import MapBuilderConfig
from mettagrid.mapgen.area import AreaWhere
from mettagrid.mapgen.mapgen import MapGen
from mettagrid.mapgen.random.int import IntConstantDistribution
from mettagrid.mapgen.scene import ChildrenAction, Scene, SceneConfig
from mettagrid.mapgen.scenes.asteroid_mask import AsteroidMaskConfig
from mettagrid.mapgen.scenes.biome_caves import BiomeCavesConfig
from mettagrid.mapgen.scenes.biome_city import BiomeCityConfig
from mettagrid.mapgen.scenes.biome_desert import BiomeDesertConfig
from mettagrid.mapgen.scenes.biome_forest import BiomeForestConfig
from mettagrid.mapgen.scenes.biome_plains import BiomePlainsConfig
from mettagrid.mapgen.scenes.bounded_layout import BoundedLayout
from mettagrid.mapgen.scenes.bsp import BSPConfig, BSPLayout
from mettagrid.mapgen.scenes.building_distributions import DistributionConfig, UniformExtractorParams
from mettagrid.mapgen.scenes.compound import CompoundConfig
from mettagrid.mapgen.scenes.ensure_hub_reachable_junction import EnsureHubReachableJunctionConfig
from mettagrid.mapgen.scenes.four_corner_compounds import FourCornerCompoundsConfig
from mettagrid.mapgen.scenes.make_connected import MakeConnected
from mettagrid.mapgen.scenes.map_corner_placements import MapCornerPlacements
from mettagrid.mapgen.scenes.maze import MazeConfig
from mettagrid.mapgen.scenes.perimeter_placements import PerimeterPlacements
from mettagrid.mapgen.scenes.radial_maze import RadialMaze
from mettagrid.mapgen.scenes.random_scene import RandomScene, RandomSceneCandidate, RandomSceneConfig


def find_biome_arena(builder: MapBuilderConfig | SceneConfig) -> "BiomeArenaConfig | None":
    """Unwrap nested MapGen.Config layers and return the BiomeArenaConfig, if any."""
    if not isinstance(builder, MapGen.Config) or builder.instance is None:
        return None
    inst = builder.instance
    if isinstance(inst, MapGen.Config) and inst.instance is not None:
        inst = inst.instance
    return inst if isinstance(inst, BiomeArenaConfig) else None


class BiomeArenaConfig(SceneConfig):
    # Core composition
    spawn_count: int

    # Biome / dungeon structure
    base_biome: str = "plains"
    base_biome_config: dict[str, Any] = {}

    #### Building placement ####

    # How much of the map is covered by buildings
    building_coverage: float = 0.05
    # Resource placement (building-based API)
    # Defines the set of buildings that can be placed on the map
    building_names: list[str] | None = None
    # What proportion of buildings are of a type, falls back to default if not set
    # If building_names is not set, this is used to determine the buildings
    building_weights: dict[str, float] | None = None

    # Hub config. `spawn_count` will be set based on `spawn_count` in this config.
    # Used when `compounds` is empty (default single-hub layout).
    hub: CompoundConfig = CompoundConfig(
        hub_object="empty",
        corner_bundle="none",
        cross_bundle="none",
        cross_distance=7,
    )

    # Multi-compound layout. Each entry is (location, CompoundConfig).
    # Locations: "center", "nw", "ne", "sw", "se".
    # "center" places the compound in the full area (default single-hub layout).
    # Corner locations use FourCornerCompounds for quadrant placement.
    compounds: list[tuple[str, CompoundConfig]] = Field(
        default_factory=lambda: [
            (
                "center",
                CompoundConfig(
                    hub_object="empty",
                    corner_bundle="none",
                    cross_bundle="none",
                    cross_distance=7,
                ),
            )
        ]
    )

    # Optional asteroid-shaped boundary mask.
    asteroid_mask: AsteroidMaskConfig | None = None

    # Objects to place at map corners (not Compound corners). List of (object_name, corner_index).
    # Corner indices: 0=top-left, 1=top-right, 2=bottom-left, 3=bottom-right.
    map_corner_placements: list[tuple[str, int]] = []
    # Inset used for map_corner_placements.
    map_corner_offset: int = 2
    # Objects to place randomly on the perimeter (object_name, count).
    map_perimeter_placements: list[tuple[str, int]] = []

    #### Layers ####

    biome_weights: dict[str, float] | None = None
    dungeon_weights: dict[str, float] | None = None
    biome_count: int | None = None
    dungeon_count: int | None = None
    density_scale: float = 0.9
    max_biome_zone_fraction: float = 0.27
    max_dungeon_zone_fraction: float = 0.2

    #### Distributions ####

    # How buildings are distributed on the map
    distribution: DistributionConfig = DistributionConfig()

    # How buildings are distributed on the map per building type, falls back to global distribution if not set
    building_distributions: dict[str, DistributionConfig] | None = None


class BiomeArena(Scene[BiomeArenaConfig]):
    def render(self) -> None:
        # No direct drawing; composition is done via children actions
        return

    def get_children(self) -> list[ChildrenAction]:
        cfg = self.config

        # Base biome map
        biome_map: dict[str, type[SceneConfig]] = {
            "caves": BiomeCavesConfig,
            "forest": BiomeForestConfig,
            "desert": BiomeDesertConfig,
            "city": BiomeCityConfig,
            "plains": BiomePlainsConfig,
        }
        if cfg.base_biome not in biome_map:
            raise ValueError(f"Unknown base_biome '{cfg.base_biome}'. Valid: {sorted(biome_map)}")
        BaseCfgModel: type[SceneConfig] = biome_map[cfg.base_biome]
        base_cfg: SceneConfig = BaseCfgModel.model_validate(cfg.base_biome_config or {})

        # Building weights
        default_building_weights: dict[str, float] = {}

        weights_dict: dict[str, float] = (
            {str(k): v for k, v in cfg.building_weights.items()} if cfg.building_weights is not None else {}
        )
        if not weights_dict:
            if cfg.building_names is not None:
                weights_dict = {name: default_building_weights.get(name, 1.0) for name in cfg.building_names}
            else:
                weights_dict = {k: v for k, v in default_building_weights.items()}

        building_names_final = list(dict.fromkeys(list((cfg.building_names or list(weights_dict)))))
        building_weights_final = {
            name: weights_dict.get(name, default_building_weights.get(name, 1.0)) for name in building_names_final
        }

        # Autoscale counts
        def _autoscale_zone_counts(
            w: int, h: int, *, biome_density: float = 1.0, dungeon_density: float = 1.0
        ) -> tuple[int, int]:
            area = max(1, w * h)
            biome_divisor = max(800, int(1600 / max(0.1, biome_density)))
            dungeon_divisor = max(800, int(1500 / max(0.1, dungeon_density)))
            biomes = max(3, min(48, area // biome_divisor))
            dungeons = max(3, min(48, area // dungeon_divisor))
            return int(biomes), int(dungeons)

        biome_count = cfg.biome_count
        dungeon_count = cfg.dungeon_count
        if biome_count is None or dungeon_count is None:
            auto_biomes, auto_dungeons = _autoscale_zone_counts(
                self.width, self.height, biome_density=cfg.density_scale, dungeon_density=cfg.density_scale
            )
            biome_count = auto_biomes if biome_count is None else biome_count
            dungeon_count = auto_dungeons if dungeon_count is None else dungeon_count

        def _min_count_for_fraction(frac: float) -> int:
            if frac <= 0:
                return 1
            return int(np.ceil(1.0 / min(0.9, max(0.02, float(frac)))))

        biome_count = max(int(biome_count), _min_count_for_fraction(cfg.max_biome_zone_fraction))
        dungeon_count = max(int(dungeon_count), _min_count_for_fraction(cfg.max_dungeon_zone_fraction))

        # Candidates
        def _make_biome_candidates(weights: dict[str, float] | None) -> list[RandomSceneCandidate]:
            defaults = {"caves": 0.0, "forest": 1.0, "desert": 1.0, "city": 1.0, "plains": 1.0}
            w = {**defaults, **(weights or {})}
            cands: list[RandomSceneCandidate] = []
            if w.get("caves", 0) > 0:
                cands.append(RandomSceneCandidate(scene=BiomeCavesConfig(), weight=w["caves"]))
            if w.get("forest", 0) > 0:
                cands.append(RandomSceneCandidate(scene=BiomeForestConfig(), weight=w["forest"]))
            if w.get("desert", 0) > 0:
                cands.append(RandomSceneCandidate(scene=BiomeDesertConfig(), weight=w["desert"]))
            if w.get("city", 0) > 0:
                cands.append(RandomSceneCandidate(scene=BiomeCityConfig(), weight=w["city"]))
            if w.get("plains", 0) > 0:
                cands.append(RandomSceneCandidate(scene=BiomePlainsConfig(), weight=w["plains"]))
            return cands

        def _make_dungeon_candidates(weights: dict[str, float] | None) -> list[RandomSceneCandidate]:
            defaults = {"bsp": 0.0, "maze": 1.0, "radial": 1.0}
            w = {**defaults, **(weights or {})}
            cands: list[RandomSceneCandidate] = []
            if w.get("bsp", 0) > 0:
                cands.append(
                    RandomSceneCandidate(
                        scene=BSPConfig(
                            rooms=4,
                            min_room_size=6,
                            min_room_size_ratio=0.35,
                            max_room_size_ratio=0.75,
                        ),
                        weight=w["bsp"],
                    )
                )
            if w.get("maze", 0) > 0:
                maze_weight = w["maze"]
                cands.append(
                    RandomSceneCandidate(
                        scene=MazeConfig(
                            algorithm="dfs",
                            room_size=IntConstantDistribution(value=3),
                            wall_size=IntConstantDistribution(value=1),
                        ),
                        weight=maze_weight * 0.6,
                    )
                )
                cands.append(
                    RandomSceneCandidate(
                        scene=MazeConfig(
                            algorithm="kruskal",
                            room_size=IntConstantDistribution(value=3),
                            wall_size=IntConstantDistribution(value=1),
                        ),
                        weight=maze_weight * 0.4,
                    )
                )
            if w.get("radial", 0) > 0:
                cands.append(
                    RandomSceneCandidate(
                        scene=RadialMaze.Config(arms=8, arm_width=1, clear_background=False, outline_walls=False),
                        weight=w["radial"],
                    )
                )
            return cands

        biome_max_w = max(10, int(min(self.width * cfg.max_biome_zone_fraction, self.width // 2)))
        biome_max_h = max(10, int(min(self.height * cfg.max_biome_zone_fraction, self.height // 2)))
        dungeon_max_w = max(10, int(min(self.width * cfg.max_dungeon_zone_fraction, self.width // 2)))
        dungeon_max_h = max(10, int(min(self.height * cfg.max_dungeon_zone_fraction, self.height // 2)))

        def _wrap_in_layout(scene_cfg: SceneConfig, tag: str, max_w: int, max_h: int) -> SceneConfig:
            return BoundedLayout.Config(
                max_width=max_w,
                max_height=max_h,
                tag=tag,
                children=[
                    ChildrenAction(
                        scene=scene_cfg,
                        where=AreaWhere(tags=[tag]),
                        limit=1,
                        order_by="first",
                    )
                ],
            )

        biome_layer: ChildrenAction | None = None
        biome_cands = _make_biome_candidates(cfg.biome_weights)
        if biome_cands:
            biome_fill_count = max(1, int(biome_count * 0.6))
            biome_layer = ChildrenAction(
                scene=BSPLayout.Config(
                    area_count=biome_count,
                    children=[
                        ChildrenAction(
                            scene=_wrap_in_layout(
                                RandomScene.Config(candidates=biome_cands),
                                tag="biome.zone",
                                max_w=biome_max_w,
                                max_h=biome_max_h,
                            ),
                            where=AreaWhere(tags=["zone"]),
                            order_by="random",
                            limit=biome_fill_count,
                        )
                    ],
                ),
                where="full",
            )

        dungeon_layer: ChildrenAction | None = None
        dungeon_cands = _make_dungeon_candidates(cfg.dungeon_weights)
        if dungeon_cands:
            dungeon_fill_count = max(1, int(dungeon_count * 0.5))
            dungeon_layer = ChildrenAction(
                scene=BSPLayout.Config(
                    area_count=dungeon_count,
                    children=[
                        ChildrenAction(
                            scene=_wrap_in_layout(
                                RandomSceneConfig(candidates=dungeon_cands),
                                tag="dungeon.zone",
                                max_w=dungeon_max_w,
                                max_h=dungeon_max_h,
                            ),
                            where=AreaWhere(tags=["zone"]),
                            order_by="random",
                            limit=dungeon_fill_count,
                        )
                    ],
                ),
                where="full",
                order_by="first",
                limit=1,
            )

        children: list[ChildrenAction] = []

        # Base shell first
        children.append(ChildrenAction(scene=base_cfg, where="full"))

        if biome_layer is not None:
            children.append(biome_layer)
        if dungeon_layer is not None:
            children.append(dungeon_layer)

        asteroid_mask = cfg.asteroid_mask
        if asteroid_mask is None and min(self.width, self.height) >= 80:
            asteroid_mask = AsteroidMaskConfig()
        if asteroid_mask is not None:
            children.append(ChildrenAction(scene=asteroid_mask, where="full"))

        if building_names_final:
            children.append(
                ChildrenAction(
                    scene=UniformExtractorParams(
                        target_coverage=cfg.building_coverage,
                        building_names=building_names_final,
                        building_weights=building_weights_final,
                        clear_existing=False,
                        distribution=cfg.distribution,
                        building_distributions=cfg.building_distributions,
                    ),
                    where="full",
                )
            )

        # Connectivity + hub
        children.append(
            ChildrenAction(
                scene=cfg.hub.model_copy(deep=True, update={"spawn_count": cfg.spawn_count}),
                where="full",
            )
        )

        children.append(
            ChildrenAction(
                scene=MakeConnected.Config(),
                where="full",
            )
        )

        if cfg.map_perimeter_placements:
            children.append(
                ChildrenAction(
                    scene=PerimeterPlacements.Config(placements=cfg.map_perimeter_placements, offset=2),
                    where="full",
                )
            )
        if cfg.map_corner_placements:
            children.append(
                ChildrenAction(
                    scene=MapCornerPlacements.Config(
                        placements=cfg.map_corner_placements,
                        offset=cfg.map_corner_offset,
                    ),
                    where="full",
                )
            )

        return children


class SequentialBiomeArenaConfig(BiomeArenaConfig):
    _scene_cls = None


class SequentialBiomeArena(Scene[SequentialBiomeArenaConfig]):
    def render(self) -> None:
        pass

    def get_children(self) -> list[ChildrenAction]:
        cfg = self.config
        biome_map: dict[str, type[SceneConfig]] = {
            "caves": BiomeCavesConfig,
            "forest": BiomeForestConfig,
            "desert": BiomeDesertConfig,
            "city": BiomeCityConfig,
            "plains": BiomePlainsConfig,
        }
        BaseCfgModel = biome_map.get(cfg.base_biome)
        if BaseCfgModel is None:
            raise ValueError(f"Unknown base_biome '{cfg.base_biome}'. Valid: {sorted(biome_map)}")
        base_cfg: SceneConfig = BaseCfgModel.model_validate(cfg.base_biome_config or {})
        default_building_weights: dict[str, float] = {}
        weights_dict: dict[str, float] = {str(k): v for k, v in (cfg.building_weights or {}).items()}
        if not weights_dict:
            names = cfg.building_names or list(default_building_weights)
            weights_dict = {name: default_building_weights.get(name, 1.0) for name in names}
        building_names_final = list(dict.fromkeys(cfg.building_names or list(weights_dict)))
        building_weights_final = {
            name: weights_dict.get(name, default_building_weights.get(name, 1.0)) for name in building_names_final
        }

        def _make_biomes(weights: dict[str, float] | None) -> list[SceneConfig]:
            if weights is not None and "none" in weights:
                return []
            defaults = {"caves": 0.0, "forest": 1.0, "desert": 1.0, "city": 1.0, "plains": 1.0}
            w = {**defaults, **(weights or {})}
            biome_defs = [
                ("caves", BiomeCavesConfig()),
                ("forest", BiomeForestConfig()),
                ("desert", BiomeDesertConfig()),
                ("city", BiomeCityConfig()),
                ("plains", BiomePlainsConfig()),
            ]
            return [cfg for key, cfg in biome_defs if float(w.get(key, 0.0)) > 0]

        def _make_dungeons(weights: dict[str, float] | None) -> list[SceneConfig]:
            if weights is not None and "none" in weights:
                return []
            defaults = {"maze": 1.0, "radial": 1.0}
            w = {**defaults, **(weights or {})}
            dungeons: list[SceneConfig] = []
            if float(w.get("maze", 0.0)) > 0:
                dungeons.append(
                    RandomScene.Config(
                        candidates=[
                            RandomSceneCandidate(
                                scene=MazeConfig(
                                    algorithm="dfs",
                                    room_size=IntConstantDistribution(value=3),
                                    wall_size=IntConstantDistribution(value=1),
                                ),
                                weight=0.6,
                            ),
                            RandomSceneCandidate(
                                scene=MazeConfig(
                                    algorithm="kruskal",
                                    room_size=IntConstantDistribution(value=3),
                                    wall_size=IntConstantDistribution(value=1),
                                ),
                                weight=0.4,
                            ),
                        ]
                    )
                )
            if float(w.get("radial", 0.0)) > 0:
                dungeons.append(RadialMaze.Config(arms=8, arm_width=1, clear_background=False, outline_walls=False))
            return dungeons

        biome_max_w = max(10, int(min(self.width * cfg.max_biome_zone_fraction, self.width // 2)))
        biome_max_h = max(10, int(min(self.height * cfg.max_biome_zone_fraction, self.height // 2)))
        dungeon_max_w = max(10, int(min(self.width * cfg.max_dungeon_zone_fraction, self.width // 2)))
        dungeon_max_h = max(10, int(min(self.height * cfg.max_dungeon_zone_fraction, self.height // 2)))

        def _wrap_in_layout(scene_cfg: SceneConfig, tag: str, max_w: int, max_h: int) -> SceneConfig:
            return BoundedLayout.Config(
                max_width=max_w,
                max_height=max_h,
                tag=tag,
                children=[
                    ChildrenAction(
                        scene=scene_cfg,
                        where=AreaWhere(tags=[tag]),
                        limit=1,
                        order_by="first",
                    )
                ],
            )

        def _make_layer(
            configs: list[SceneConfig],
            tag: str,
            max_w: int,
            max_h: int,
        ) -> ChildrenAction | None:
            if not configs:
                return None
            children = [
                ChildrenAction(
                    scene=_wrap_in_layout(scene_cfg, tag=tag, max_w=max_w, max_h=max_h),
                    where=AreaWhere(tags=["zone"]),
                    order_by="random",
                    limit=1,
                    lock=tag,
                )
                for scene_cfg in configs
            ]
            return ChildrenAction(
                scene=BSPLayout.Config(
                    area_count=len(configs),
                    children=children,
                ),
                where="full",
            )

        biomes = _make_biomes(cfg.biome_weights)
        dungeons = _make_dungeons(cfg.dungeon_weights)
        biome_layer = _make_layer(biomes, "biome.zone", biome_max_w, biome_max_h) if biomes else None
        dungeon_layer = _make_layer(dungeons, "dungeon.zone", dungeon_max_w, dungeon_max_h) if dungeons else None
        children: list[ChildrenAction] = []
        children.append(ChildrenAction(scene=base_cfg, where="full"))
        if biome_layer is not None:
            children.append(biome_layer)
        if dungeon_layer is not None:
            children.append(dungeon_layer)
        asteroid_mask = cfg.asteroid_mask
        if asteroid_mask is None and min(self.width, self.height) >= 80:
            asteroid_mask = AsteroidMaskConfig()
        if asteroid_mask is not None:
            children.append(ChildrenAction(scene=asteroid_mask, where="full"))
        if building_names_final:
            children.append(
                ChildrenAction(
                    scene=UniformExtractorParams(
                        target_coverage=cfg.building_coverage,
                        building_names=building_names_final,
                        building_weights=building_weights_final,
                        clear_existing=False,
                        distribution=cfg.distribution,
                        building_distributions=cfg.building_distributions,
                    ),
                    where="full",
                )
            )
        # Separate center compounds (placed directly) from corner compounds (quadrant layout).
        center_compounds = [(loc, c) for loc, c in cfg.compounds if loc == "center"]
        corner_compounds = [(loc, c) for loc, c in cfg.compounds if loc != "center"]

        if corner_compounds:
            loc_to_index = {"nw": 0, "ne": 1, "sw": 2, "se": 3}
            compound_cfgs: list[tuple[int, CompoundConfig]] = [
                (loc_to_index[loc], compound.model_copy(deep=True)) for loc, compound in corner_compounds
            ]
            spawns_per_compound = max(1, cfg.spawn_count // max(1, len(compound_cfgs)))
            fcc = FourCornerCompoundsConfig(
                compound=compound_cfgs[0][1],
                num_compounds=len(compound_cfgs),
                spawn_count=spawns_per_compound,
            )
            fcc.hub_objects = [c.hub_object for _, c in compound_cfgs]
            fcc.spawn_symbols = [c.spawn_symbol for _, c in compound_cfgs]
            fcc.stations_per_compound = [list(c.stations) for _, c in compound_cfgs]
            children.append(ChildrenAction(scene=fcc, where="full"))

        for _loc, _compound in center_compounds:
            # Center compounds use cfg.hub (which variants like TeamHubVariant modify).
            children.append(
                ChildrenAction(
                    scene=cfg.hub.model_copy(deep=True, update={"spawn_count": cfg.spawn_count}),
                    where="full",
                )
            )
        children.append(
            ChildrenAction(
                scene=MakeConnected.Config(),
                where="full",
            )
        )
        if cfg.map_perimeter_placements:
            children.append(
                ChildrenAction(
                    scene=PerimeterPlacements.Config(placements=cfg.map_perimeter_placements, offset=2),
                    where="full",
                )
            )
        if cfg.map_corner_placements:
            children.append(
                ChildrenAction(
                    scene=MapCornerPlacements.Config(
                        placements=cfg.map_corner_placements,
                        offset=cfg.map_corner_offset,
                    ),
                    where="full",
                )
            )
        children.append(
            ChildrenAction(
                scene=EnsureHubReachableJunctionConfig(max_distance=15),
                where="full",
            )
        )
        return children
