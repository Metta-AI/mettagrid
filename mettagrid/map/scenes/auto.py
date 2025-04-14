from dataclasses import dataclass, field
from typing import Any
import numpy as np
from omegaconf import Node
from mettagrid.map.scene import Scene, TypedChild
from mettagrid.map.scenes.bsp import BSPLayout
from mettagrid.map.scenes.make_connected import MakeConnected
from mettagrid.map.scenes.maze import MazeKruskal
from mettagrid.map.scenes.mirror import Mirror
from mettagrid.map.scenes.random import Random
from mettagrid.map.scenes.room_grid import RoomGrid
from mettagrid.map.scenes.wfc import WFC


# Global config for convenience.
@dataclass
class AutoConfig:
    num_agents: int = 0
    wfc_patterns: list[str] = field(default_factory=list)
    grid: Any = field(default_factory=dict)
    room_symmetry: Any = field(default_factory=dict)
    content: Any = field(default_factory=dict)
    maze: Any = field(default_factory=dict)
    # TODO - stricter types


class BaseAuto(Scene):
    def __init__(self, config: AutoConfig):
        super().__init__(children=[])
        self._config = config

    def _render(self, node: Node):
        pass


class Auto(BaseAuto):
    def get_children(self, node) -> list[TypedChild]:
        return [
            {"scene": AutoLayout(config=self._config), "where": "full"},
            {"scene": MakeConnected(), "where": "full"},
            {"scene": Random(agents=self._config.num_agents), "where": "full"},
        ]


class AutoLayout(BaseAuto):
    def get_children(self, node) -> list[TypedChild]:
        weights = [0.1, 0.9]
        layout = np.random.choice(["grid", "bsp"], p=weights)

        if layout == "grid":
            rows = np.random.randint(
                self._config.grid.min_rows, self._config.grid.max_rows + 1
            )
            columns = np.random.randint(
                self._config.grid.min_columns, self._config.grid.max_columns + 1
            )

            return [
                {
                    "scene": RoomGrid(
                        rows=rows,
                        columns=columns,
                        border_width=0,  # TODO - randomize?
                        children=[
                            {
                                "scene": AutoSymmetry(config=self._config),
                                "where": {"tags": ["room"]},
                            }
                        ],
                    ),
                    "where": "full",
                },
            ]
        elif layout == "bsp":
            return [
                {
                    "scene": BSPLayout(
                        area_count=9,
                        children=[
                            {
                                "scene": AutoSymmetry(config=self._config),
                                "where": {"tags": ["zone"]},
                            }
                        ],
                    ),  # TODO - configurable
                    "where": "full",
                }
            ]
        else:
            raise ValueError(f"Invalid layout: {layout}")


class AutoSymmetry(BaseAuto):
    def get_children(self, node) -> list[TypedChild]:
        weights = np.array(
            [
                self._config.room_symmetry.none,
                self._config.room_symmetry.horizontal,
                self._config.room_symmetry.vertical,
                self._config.room_symmetry.x4,
            ],
            dtype=np.float32,
        )
        weights /= weights.sum()
        symmetry = np.random.choice(["none", "horizontal", "vertical", "x4"], p=weights)
        scene = AutoContent(config=self._config)
        if symmetry != "none":
            scene = Mirror(scene, symmetry)
        return [{"scene": scene, "where": "full"}]


class AutoContent(BaseAuto):
    def get_children(self, node) -> list[TypedChild]:
        candidates = ["maze", "wfc"]
        weights = np.array(
            [self._config.content.maze, self._config.content.wfc], dtype=np.float32
        )
        weights /= weights.sum()
        choice = np.random.choice(candidates, p=weights)

        if choice == "maze":
            wall_size = np.random.randint(
                self._config.maze.min_wall_size,
                self._config.maze.max_wall_size + 1,
            )
            cell_size = np.random.randint(
                self._config.maze.min_cell_size,
                self._config.maze.max_cell_size + 1,
            )
            scene = MazeKruskal(wall_size, cell_size)
        else:
            pattern = np.random.choice(self._config.wfc_patterns)
            scene = WFC(
                pattern=pattern,
                pattern_size=3,
            )

        return [{"scene": scene, "where": "full"}]
