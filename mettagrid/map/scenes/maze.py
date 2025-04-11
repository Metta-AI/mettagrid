import random
from typing import Any, List, Literal, Tuple, Union

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

class MazeKruskal(Scene):
    """
    Maze generation using Randomized Kruskal's algorithm.

    The generated maze doesn't have an outer border.

    Example output:
    ┌─────────┐
    │         │
    │ # ##### │
    │ # # #   │
    │#### ### │
    │   # # # │
    │ ### # # │
    │         │
    │## ### ##│
    │     #   │
    └─────────┘

    It's preferred that width and height are odd. If they are even, last row and/or column will be walled off. You can override this by setting extra_space_empty=True.
    """
    EMPTY, WALL = "empty", "wall"

    def __init__(self, extra_space_empty: bool = False, seed=None, children: list[Any] = []):
        super().__init__(children=children)
        self._extra_space_empty = extra_space_empty
        self._rng = random.Random(seed)

    def _render(self, node: Node):
        grid = node.grid
        width = node.width
        height = node.height
        grid[:] = self.WALL

        print(width, height, self._extra_space_empty)

        if width % 2 == 0:
            width -= 1
            if self._extra_space_empty:
                grid[-1, :] = self.EMPTY

        if height % 2 == 0:
            height -= 1
            if self._extra_space_empty:
                grid[:, -1] = self.EMPTY

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
            x, y = anchor_to_position(anchor, width, height)
            node.make_area(x, y, 1, 1, tags=[anchor])

        return grid
