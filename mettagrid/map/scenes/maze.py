import random
from typing import Literal, Tuple, Union

from mettagrid.config.room.utils import create_grid, set_position
from mettagrid.map.scene import Scene
from mettagrid.map.node import Node

Anchor = Union[Literal["top-left"], Literal["top-right"], Literal["bottom-left"], Literal["bottom-right"]]

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
    START, END = "agent.agent", "altar"

    _start_pos: Anchor
    _end_pos: Anchor

    def __init__(self, start_pos: Anchor = "top-left", end_pos: Anchor = "bottom-right", seed=None):
        super().__init__()
        self._rng = random.Random(seed)
        self._start_pos = start_pos
        self._end_pos = end_pos

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

        sx, sy = anchor_to_position(self._start_pos, width, height)
        ex, ey = anchor_to_position(self._end_pos, width, height)
        grid[sy, sx] = self.START
        grid[ey, ex] = self.END

        return grid
