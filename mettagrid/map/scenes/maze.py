import random
from typing import Any, List, Literal, Tuple, Union

from mettagrid.config.room.utils import create_grid, set_position
from mettagrid.map.scene import Scene
from mettagrid.map.node import Node

Anchor = Union[Literal["top-left"], Literal["top-right"], Literal["bottom-left"], Literal["bottom-right"]]

ALL_ANCHORS: List[Anchor] = ["top-left", "top-right", "bottom-left", "bottom-right"]

def anchor_to_position(anchor: Anchor, width: int, height: int) -> Tuple[int, int]:
    if anchor == "top-left":
        return (0, 0)
    elif anchor == "top-right":
        return (width - 1, 0)
    elif anchor == "bottom-left":
        return (0, height - 1)
    elif anchor == "bottom-right":
        return (width - 1, height - 1)

# Maze generation using Randomized Kruskal's algorithm
class MazeKruskal(Scene):
    EMPTY, WALL = "empty", "wall"

    def __init__(self, seed=None, children: list[Any] = []):
        super().__init__(children=children)
        self._rng = random.Random(seed)

    def _render(self, node: Node):
        grid = node.grid
        width = node.width
        height = node.height
        grid[:] = self.WALL

        cells = [(x, y) for y in range(0, height, 2) for x in range(0, width, 2)]
        for (x, y) in cells:
            grid[y, x] = self.EMPTY

        parent = {cell: cell for cell in cells}

        def find(cell):
            if parent[cell] != cell:
                parent[cell] = find(parent[cell])
            return parent[cell]

        def union(c1, c2):
            parent[find(c2)] = find(c1)

        walls = []
        for (x, y) in cells:
            for dx, dy in [(2, 0), (0, 2)]:
                nx, ny = x + dx, y + dy
                if nx < width and ny < height:
                    wx, wy = (x + nx) // 2, (y + ny) // 2
                    walls.append(((x, y), (nx, ny), (wx, wy)))

        self._rng.shuffle(walls)

        for cell1, cell2, wall in walls:
            if find(cell1) != find(cell2):
                wx, wy = wall
                grid[wy, wx] = self.EMPTY
                union(cell1, cell2)

        for anchor in ALL_ANCHORS:
            x, y = anchor_to_position(anchor, node.width, node.height)
            node.make_area(x, y, 1, 1, tags=[anchor])

        return grid
