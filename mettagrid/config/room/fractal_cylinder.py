"""
This file defines the FractalCylinder environment.
It creates a grid world with a fractal arrangement of cylinders.
Each cylinder is a simple object with two parallel walls.
"""

from typing import List, Optional, Tuple

import numpy as np

from mettagrid.config.room.room import Room


class Cylinder:
    """A simple cylinder defined by two parallel walls"""

    def __init__(self, x: int, y: int, length: int, width: int = 2, is_horizontal: bool = False):
        self.x = x
        self.y = y
        self.length = length
        self.width = width
        self.is_horizontal = is_horizontal

    def get_walls(self) -> List[Tuple[int, int]]:
        """Returns the positions of all wall cells in the cylinder"""
        walls = []
        if self.is_horizontal:
            # Top wall
            for i in range(-self.length // 2, self.length // 2 + 1):
                walls.append((self.x + i, self.y - self.width // 2))
            # Bottom wall
            for i in range(-self.length // 2, self.length // 2 + 1):
                walls.append((self.x + i, self.y + self.width // 2))
        else:
            # Left wall
            for i in range(-self.length // 2, self.length // 2 + 1):
                walls.append((self.x - self.width // 2, self.y + i))
            # Right wall
            for i in range(-self.length // 2, self.length // 2 + 1):
                walls.append((self.x + self.width // 2, self.y + i))
        return walls

    def get_center(self) -> Tuple[int, int]:
        """Returns the center position of the cylinder"""
        return (self.x, self.y)


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
        min_cylinder_length: int = 5,
    ):
        super().__init__(border_width=border_width, border_object=border_object)
        self._rng = np.random.default_rng(seed)
        self._width = width
        self._height = height
        self._agents = agents
        self._recursion_depth = recursion_depth
        self._min_cylinder_length = min_cylinder_length

    def _build(self) -> np.ndarray:
        # Create an empty grid
        grid = np.full((self._height, self._width), "empty", dtype=object)

        # Generate the fractal cylinder pattern
        cylinders = self._generate_fractal_cylinders(0, 0, self._width, self._height, self._recursion_depth)

        # Place all cylinders on the grid
        for cylinder in cylinders:
            # Place walls
            for x, y in cylinder.get_walls():
                if 0 <= x < self._width and 0 <= y < self._height:
                    grid[y, x] = "wall"
            # Place altar in center
            center_x, center_y = cylinder.get_center()
            if 0 <= center_x < self._width and 0 <= center_y < self._height:
                grid[center_y, center_x] = "altar"

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

    def _generate_fractal_cylinders(self, x: int, y: int, width: int, height: int, depth: int) -> List[Cylinder]:
        """Recursively generates a list of cylinders in a fractal pattern"""
        cylinders = []

        if depth == 0 or width < self._min_cylinder_length or height < self._min_cylinder_length:
            return cylinders

        # Calculate cylinder dimensions
        cylinder_length = min(width, height) // 3
        if cylinder_length < self._min_cylinder_length:
            return cylinders

        # Place central cylinder (random orientation)
        center_x = x + width // 2
        center_y = y + height // 2
        is_horizontal = self._rng.random() < 0.5
        cylinders.append(Cylinder(center_x, center_y, cylinder_length, is_horizontal=is_horizontal))

        # Calculate positions for surrounding cylinders
        spacing = max(width, height) // 3
        positions = [
            (center_x - spacing, center_y),  # Left
            (center_x + spacing, center_y),  # Right
            (center_x, center_y - spacing),  # Top
            (center_x, center_y + spacing),  # Bottom
        ]

        # Place surrounding cylinders (alternating orientations)
        for i, (pos_x, pos_y) in enumerate(positions):
            if 0 <= pos_x < self._width and 0 <= pos_y < self._height:
                # Alternate between horizontal and vertical
                is_horizontal = i % 2 == 0
                cylinders.append(Cylinder(pos_x, pos_y, cylinder_length // 2, is_horizontal=is_horizontal))

        # Recursively generate cylinders in each quadrant
        half_width = width // 2
        half_height = height // 2

        # Top-left quadrant
        cylinders.extend(self._generate_fractal_cylinders(x, y, half_width, half_height, depth - 1))
        # Top-right quadrant
        cylinders.extend(self._generate_fractal_cylinders(x + half_width, y, half_width, half_height, depth - 1))
        # Bottom-left quadrant
        cylinders.extend(self._generate_fractal_cylinders(x, y + half_height, half_width, half_height, depth - 1))
        # Bottom-right quadrant
        cylinders.extend(
            self._generate_fractal_cylinders(x + half_width, y + half_height, half_width, half_height, depth - 1)
        )

        return cylinders

    def _choose_random_empty(self, grid: np.ndarray) -> Optional[Tuple[int, int]]:
        """Returns a random empty position in the grid"""
        empty_positions = np.argwhere(grid == "empty")
        if len(empty_positions) == 0:
            return None
        return tuple(empty_positions[self._rng.integers(0, len(empty_positions))])
