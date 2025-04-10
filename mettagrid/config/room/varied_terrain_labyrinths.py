"""
This file defines the VariedTerrainLabyrinths environment.
It creates a grid world with configurable parameters, including:
  - Large obstacles and small obstacles: randomly generated, connected shapes based on target block counts.
  - Cross obstacles: cross‐shaped objects whose width and height are each sampled between 1 and 8.
  - Mini labyrinths: maze‐like structures (approximately 11×11) generated via recursive backtracking.
      After maze generation, passages are "thickened" with a probability sampled uniformly 
      from 0.3 to 1.0 – resulting in a distribution from dense (narrow passages) to sparse (wide passages).
      In addition, border gaps are forced to be at least two cells wide to allow entry/exit,
      and each empty cell has a 30% chance to be replaced with "heart".
  - Scattered single walls: individual wall cells randomly placed.
  - Altars: objects placed with a configurable number of hearts.
  - A clumpiness factor biases object placement.
Objects are placed with at least one-cell clearance.
The build order is: mini labyrinths → obstacles (large, small, crosses) → scattered single walls → remaining objects and agents.
"""

from typing import Optional
import numpy as np
from omegaconf import DictConfig
from mettagrid.config.room.room import Room

class VariedTerrainLabyrinths(Room):
    def __init__(
        self,
        width: int,
        height: int,
        objects: DictConfig,
        agents: int | DictConfig = 0,
        seed: Optional[int] = None,
        border_width: int = 0,
        border_object: str = "wall",
        **kwargs  # Accept extra parameters
    ):
        super().__init__(border_width=border_width, border_object=border_object)
        self._rng = np.random.default_rng(seed)
        self._width = width
        self._height = height
        self._objects = objects
        self._agents = agents

        # Parameters for obstacle types.
        self._large_obstacles = kwargs.pop("large_obstacles", {"size_range": [10, 25], "count": 0})
        self._small_obstacles = kwargs.pop("small_obstacles", {"size_range": [3, 6], "count": 0})
        self._crosses = kwargs.pop("crosses", {"count": 0})
        # Altars: number of altars (heart objects) is overridden by hearts_count.
        self._hearts_count = kwargs.pop("hearts_count", 50)
        self._clumpiness = kwargs.pop("clumpiness", 0)
        # Labyrinths: number of mini labyrinths (mazes) to scatter.
        self._labyrinths = kwargs.pop("labyrinths", {"count": 0})
        # Scattered single walls.
        self._scattered_walls = kwargs.pop("scattered_walls", {"count": 0})

    def _build(self):
        # Prepare agent symbols.
        if isinstance(self._agents, int):
            agents = ["agent.agent"] * self._agents
        elif isinstance(self._agents, dict) or isinstance(self._agents, DictConfig):
            agents = ["agent." + agent for agent, na in self._agents.items() for _ in range(na)]
        else:
            agents = []

        # Adjust object counts if total objects exceed 2/3 of room area.
        total_objects = sum(self._objects.values()) + len(agents)
        area = self._width * self._height
        while total_objects > 2 * area / 3:
            for obj in self._objects:
                self._objects[obj] = max(1, self._objects[obj] // 2)
            total_objects = sum(self._objects.values()) + len(agents)

        # Create an empty grid.
        grid = np.full((self._height, self._width), "empty", dtype=object)

        # --- Place mini labyrinths first ---
        grid = self._place_labyrinths(grid)
        # --- Place obstacles (large, small, crosses) ---
        grid = self._place_all_obstacles(grid)
        # --- Place scattered single wall pieces ---
        grid = self._place_scattered_walls(grid)
        # --- Place remaining objects ---
        for obj, count in self._objects.items():
            # For altars, override count with hearts_count.
            if obj == "altar":
                count = self._hearts_count
            for _ in range(count):
                pos = self._choose_empty_position(grid)
                if pos is None:
                    raise ValueError("No empty space available for object placement.")
                grid[pos[0], pos[1]] = obj
        # --- Place agents ---
        for agent in agents:
            pos = self._choose_empty_position(grid)
            if pos is None:
                raise ValueError("No empty space available for agent placement.")
            grid[pos[0], pos[1]] = agent
        return grid

    def _generate_random_shape(self, num_blocks: int) -> np.ndarray:
        """
        Generates a random connected shape with 'num_blocks' cells set to "wall"
        using a random-walk algorithm. The shape is normalized (top-left at (0,0)).
        """
        shape_cells = {(0, 0)}
        while len(shape_cells) < num_blocks:
            candidates = []
            for (r, c) in shape_cells:
                for dr, dc in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                    candidate = (r + dr, c + dc)
                    if candidate not in shape_cells:
                        candidates.append(candidate)
            if not candidates:
                break
            idx = self._rng.integers(0, len(candidates))
            new_cell = candidates[idx]
            shape_cells.add(new_cell)
        min_r = min(r for r, _ in shape_cells)
        max_r = max(r for r, _ in shape_cells)
        min_c = min(c for _, c in shape_cells)
        max_c = max(c for _, c in shape_cells)
        pattern = np.full((max_r - min_r + 1, max_c - min_c + 1), "empty", dtype=object)
        for (r, c) in shape_cells:
            pattern[r - min_r, c - min_c] = "wall"
        return pattern

    def _generate_cross_pattern(self) -> np.ndarray:
        """
        Generates a cross-shaped obstacle.
        Both the width and height are sampled between 1 and 8 (inclusive),
        and the center row and center column are set to "wall".
        """
        cross_w = self._rng.integers(1, 9)
        cross_h = self._rng.integers(1, 9)
        pattern = np.full((cross_h, cross_w), "empty", dtype=object)
        center_row = cross_h // 2
        center_col = cross_w // 2
        pattern[center_row, :] = "wall"
        pattern[:, center_col] = "wall"
        return pattern

    def _generate_labyrinth_pattern(self) -> np.ndarray:
        """
        Generates a mini labyrinth pattern.
        Dimensions are chosen randomly between 11 and 13, then clamped to 11,
        and forced to be odd (resulting in an 11×11 maze). A recursive backtracking algorithm
        carves passages. Then, passages are thickened based on a randomly sampled thickening probability 
        (between 0.3 and 1.0) – this controls how open the labyrinth is. Finally, border gaps are ensured
        to be at least two cells wide, and each empty cell has a 30% chance to be replaced with "heart".
        """
        # Choose dimensions between 11 and 13, then clamp to 11.
        h = int(self._rng.integers(11, 14))
        if h > 11: h = 11
        w = int(self._rng.integers(11, 14))
        if w > 11: w = 11
        # Ensure odd dimensions.
        if h % 2 == 0: h -= 1
        if w % 2 == 0: w -= 1

        maze = np.full((h, w), "wall", dtype=object)
        start = (1, 1)
        maze[start] = "empty"
        stack = [start]
        directions = [(-2, 0), (2, 0), (0, -2), (0, 2)]
        while stack:
            r, c = stack[-1]
            neighbors = []
            for dr, dc in directions:
                nr, nc = r + dr, c + dc
                if 0 <= nr < h and 0 <= nc < w and maze[nr, nc] == "wall":
                    neighbors.append((nr, nc))
            if neighbors:
                next_cell = neighbors[self._rng.integers(0, len(neighbors))]
                nr, nc = next_cell
                wall_r, wall_c = r + (nr - r) // 2, c + (nc - c) // 2
                maze[wall_r, wall_c] = "empty"
                maze[nr, nc] = "empty"
                stack.append(next_cell)
            else:
                stack.pop()

        # Sample a thickening probability between 0.3 and 1.0.
        thick_prob = 0.3 + 0.7 * self._rng.random()
        maze_thick = maze.copy()
        for i in range(1, h - 1):
            for j in range(1, w - 1):
                if maze[i, j] == "empty":
                    if self._rng.random() < thick_prob:
                        if j+1 < w:
                            maze_thick[i, j + 1] = "empty"
                    if self._rng.random() < thick_prob:
                        if i+1 < h:
                            maze_thick[i + 1, j] = "empty"
        maze = maze_thick

        # Ensure each border has a gap of at least 2 cells.
        if w > 3:
            contiguous = 0
            for j in range(1, w - 1):
                if maze[0, j] == "empty":
                    contiguous += 1
                else:
                    contiguous = 0
                if contiguous >= 2:
                    break
            else:
                maze[0, 1:3] = "empty"
        if w > 3:
            contiguous = 0
            for j in range(1, w - 1):
                if maze[h - 1, j] == "empty":
                    contiguous += 1
                else:
                    contiguous = 0
                if contiguous >= 2:
                    break
            else:
                maze[h - 1, 1:3] = "empty"
        if h > 3:
            contiguous = 0
            for i in range(1, h - 1):
                if maze[i, 0] == "empty":
                    contiguous += 1
                else:
                    contiguous = 0
                if contiguous >= 2:
                    break
            else:
                maze[1:3, 0] = "empty"
        if h > 3:
            contiguous = 0
            for i in range(1, h - 1):
                if maze[i, w - 1] == "empty":
                    contiguous += 1
                else:
                    contiguous = 0
                if contiguous >= 2:
                    break
            else:
                maze[1:3, w - 1] = "empty"

        # Scatter hearts with 30% probability.
        for i in range(h):
            for j in range(w):
                if maze[i, j] == "empty" and self._rng.random() < 0.3:
                    maze[i, j] = "heart"
        return maze

    def _place_labyrinths(self, grid):
        """
        Attempts to place mini labyrinths on the grid.
        The number of labyrinths is determined by self._labyrinths["count"] (typically 6–10 per map).
        For each labyrinth, a labyrinth pattern is generated and placed in a random empty region.
        If no suitable location is found, the labyrinth is skipped.
        """
        height, width = grid.shape
        labyrinth_count = self._labyrinths.get("count", 0)
        for _ in range(labyrinth_count):
            pattern = self._generate_labyrinth_pattern()
            p_h, p_w = pattern.shape
            placed = False
            attempts = 0
            max_attempts = (p_h * p_w) * 100
            while not placed and attempts < max_attempts:
                attempts += 1
                if height - p_h < 0 or width - p_w < 0:
                    break
                r = self._rng.integers(0, height - p_h + 1)
                c = self._rng.integers(0, width - p_w + 1)
                region = grid[r:r+p_h, c:c+p_w]
                if np.all(region == "empty"):
                    grid[r:r+p_h, c:c+p_w] = pattern
                    placed = True
            if not placed:
                print(f"Warning: Could not place a labyrinth after {attempts} attempts.")
        return grid

    def _place_all_obstacles(self, grid):
        """
        Places large obstacles, small obstacles, and cross obstacles on the grid.
        For each type, a target block count (or pattern) is sampled from its range;
        a random, connected shape (or cross pattern) is generated and placed with one-cell clearance.
        If there isn’t enough space, the obstacle is skipped.
        """
        height, width = grid.shape
        clearance = 1

        # --- Place large obstacles ---
        large_count = self._large_obstacles.get("count", 0)
        for _ in range(large_count):
            low, high = self._large_obstacles.get("size_range", [10, 25])
            target_blocks = self._rng.integers(low, high + 1)
            pattern = self._generate_random_shape(target_blocks)
            p_h, p_w = pattern.shape
            placed = False
            attempts = 0
            max_attempts = target_blocks * 100
            while not placed and attempts < max_attempts:
                attempts += 1
                effective_h = p_h + 2 * clearance
                effective_w = p_w + 2 * clearance
                if height - effective_h < 0 or width - effective_w < 0:
                    break
                r = self._rng.integers(0, height - effective_h + 1)
                c = self._rng.integers(0, width - effective_w + 1)
                region = grid[r:r+effective_h, c:c+effective_w]
                if np.all(region == "empty"):
                    grid[r+clearance:r+clearance+p_h, c+clearance:c+clearance+p_w] = pattern
                    placed = True
            if not placed:
                print(f"Warning: Could not place large obstacle of {target_blocks} blocks after {attempts} attempts.")

        # --- Place small obstacles ---
        small_count = self._small_obstacles.get("count", 0)
        for _ in range(small_count):
            low, high = self._small_obstacles.get("size_range", [3, 6])
            target_blocks = self._rng.integers(low, high + 1)
            pattern = self._generate_random_shape(target_blocks)
            p_h, p_w = pattern.shape
            placed = False
            attempts = 0
            max_attempts = target_blocks * 100
            while not placed and attempts < max_attempts:
                attempts += 1
                effective_h = p_h + 2 * clearance
                effective_w = p_w + 2 * clearance
                if height - effective_h < 0 or width - effective_w < 0:
                    break
                r = self._rng.integers(0, height - effective_h + 1)
                c = self._rng.integers(0, width - effective_w + 1)
                region = grid[r:r+effective_h, c:c+effective_w]
                if np.all(region == "empty"):
                    grid[r+clearance:r+clearance+p_h, c+clearance:c+clearance+p_w] = pattern
                    placed = True
            if not placed:
                print(f"Warning: Could not place small obstacle of {target_blocks} blocks after {attempts} attempts.")

        # --- Place cross obstacles ---
        crosses_count = self._crosses.get("count", 0)
        for _ in range(crosses_count):
            pattern = self._generate_cross_pattern()
            p_h, p_w = pattern.shape
            placed = False
            attempts = 0
            max_attempts = (p_h * p_w) * 100
            while not placed and attempts < max_attempts:
                attempts += 1
                if height - p_h < 0 or width - p_w < 0:
                    break
                r = self._rng.integers(0, height - p_h + 1)
                c = self._rng.integers(0, width - p_w + 1)
                region = grid[r:r+p_h, c:c+p_w]
                if np.all(region == "empty"):
                    grid[r:r+p_h, c:c+p_w] = pattern
                    placed = True
            if not placed:
                print(f"Warning: Could not place cross obstacle after {attempts} attempts.")

        return grid

    def _place_scattered_walls(self, grid):
        """
        Randomly scatters single wall cells over the grid.
        The number of scattered walls is specified by self._scattered_walls["count"].
        """
        count = self._scattered_walls.get("count", 0)
        height, width = grid.shape
        placed = 0
        attempts = 0
        max_attempts = count * 100
        while placed < count and attempts < max_attempts:
            attempts += 1
            pos = self._choose_empty_position(grid)
            if pos is None:
                break
            grid[pos[0], pos[1]] = "wall"
            placed += 1
        return grid

    def _choose_empty_position(self, grid):
        """
        Returns a random empty cell index from the grid.
        If clumpiness > 0, selection is biased toward empty cells adjacent to non-empty cells.
        """
        empty_positions = np.argwhere(grid == "empty")
        if len(empty_positions) == 0:
            return None
        if self._clumpiness > 0 and self._rng.random() < (self._clumpiness / 5.0):
            clumped = []
            for pos in empty_positions:
                r, c = pos
                neighbors = grid[max(r-1, 0):min(r+2, grid.shape[0]),
                                 max(c-1, 0):min(c+2, grid.shape[1])]
                if np.any(neighbors != "empty"):
                    clumped.append(pos)
            if clumped:
                empty_positions = np.array(clumped)
        pos_idx = self._rng.integers(0, len(empty_positions))
        return empty_positions[pos_idx]

# End of VariedTerrainLabyrinths class implementation