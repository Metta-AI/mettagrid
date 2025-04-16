"""
This file defines the FractalCylinder environment.
It creates a grid world with a fractal arrangement of cylinders.
The cylinders are arranged in a recursive pattern, with each level
containing smaller cylinders arranged around a central cylinder.
"""

from typing import Optional, Tuple

import numpy as np

from mettagrid.config.room.room import Room


class FractalCylinder(Room):
    def __init__(
        self,
        width: int,
        height: int,
        agents: int | dict = 0,
        seed: Optional[int] = None,
        border_width: int = 0,
        border_object: str = "wall",
        recursion_depth: int = 3,
        min_cylinder_size: int = 3,
    ):
        super().__init__(border_width=border_width, border_object=border_object)
        self._rng = np.random.default_rng(seed)
        self._width = width
        self._height = height
        self._agents = agents
        self._recursion_depth = recursion_depth
        self._min_cylinder_size = min_cylinder_size

    def _build(self) -> np.ndarray:
        # Create an empty grid
        grid = np.full((self._height, self._width), "empty", dtype=object)

        # Place the fractal cylinders
        self._place_fractal_cylinder(grid, 0, 0, self._width, self._height, self._recursion_depth)

        # Place agents
        if isinstance(self._agents, int):
            agents = ["agent.agent"] * self._agents
        elif isinstance(self._agents, dict):
            agents = ["agent." + agent for agent, na in self._agents.items() for _ in range(na)]
        else:
            agents = []

        for agent in agents:
            pos = self._choose_random_empty(grid)
            if pos is None:
                break
            r, c = pos
            grid[r, c] = agent

        return grid

    def _place_fractal_cylinder(self, grid: np.ndarray, x: int, y: int, width: int, height: int, depth: int) -> None:
        """Recursively places cylinders in a fractal pattern"""
        if depth == 0 or width < self._min_cylinder_size or height < self._min_cylinder_size:
            return

        # Place central cylinder
        center_x = x + width // 2
        center_y = y + height // 2
        cylinder_size = min(width, height) // 3
        self._place_cylinder(grid, center_x, center_y, cylinder_size)

        # Recursively place smaller cylinders in each quadrant
        half_width = width // 2
        half_height = height // 2

        # Top-left quadrant
        self._place_fractal_cylinder(grid, x, y, half_width, half_height, depth - 1)
        # Top-right quadrant
        self._place_fractal_cylinder(grid, x + half_width, y, half_width, half_height, depth - 1)
        # Bottom-left quadrant
        self._place_fractal_cylinder(grid, x, y + half_height, half_width, half_height, depth - 1)
        # Bottom-right quadrant
        self._place_fractal_cylinder(grid, x + half_width, y + half_height, half_width, half_height, depth - 1)

    def _place_cylinder(self, grid: np.ndarray, center_x: int, center_y: int, size: int) -> None:
        """Places a single cylinder at the specified position"""
        for r in range(center_y - size, center_y + size + 1):
            for c in range(center_x - size, center_x + size + 1):
                if 0 <= r < self._height and 0 <= c < self._width:
                    # Create a circular pattern
                    if (r - center_y) ** 2 + (c - center_x) ** 2 <= size**2:
                        grid[r, c] = "wall"

    def _choose_random_empty(self, grid: np.ndarray) -> Optional[Tuple[int, int]]:
        """Returns a random empty position in the grid"""
        empty_positions = np.argwhere(grid == "empty")
        if len(empty_positions) == 0:
            return None
        return tuple(empty_positions[self._rng.integers(0, len(empty_positions))])
