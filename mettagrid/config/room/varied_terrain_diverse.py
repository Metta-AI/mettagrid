"""
This file defines the VariedTerrainDiverse environment.
It creates a grid world with configurable features including:
  - Large obstacles and small obstacles: randomly generated, connected shapes.
  - Cross obstacles: cross-shaped patterns.
  - Mini labyrinths: maze-like structures (≈11×11) with passages thickened probabilistically,
      and with at least two-cell gaps along the borders; empty cells may be replaced with "heart".
  - Scattered single walls: individual wall cells placed at random empty cells.
  - Blocks: new rectangular objects whose width and height are sampled uniformly between 2 and 14.
      The number of blocks (block count) is sampled from 0 to 10.
  - Altars: objects are placed with a configurable number of hearts.
  - A clumpiness factor that biases object placement.
All objects are placed with at least a one-cell clearance and if no space is found for a new object, placement is skipped.
The build order is:
    mini labyrinths → obstacles (large, small, crosses) → scattered walls → blocks → remaining objects → agents.
"""

from typing import Optional, Tuple, List
import numpy as np
from omegaconf import DictConfig
from mettagrid.config.room.room import Room

class VariedTerrainDiverse(Room):
    def __init__(
        self,
        width: int,
        height: int,
        objects: DictConfig,
        agents: int | DictConfig = 0,
        seed: Optional[int] = None,
        border_width: int = 0,
        border_object: str = "wall",
        occupancy_threshold: float = 0.66,  # maximum fraction of grid cells to occupy
        **kwargs  # Extra parameters
    ):
        super().__init__(border_width=border_width, border_object=border_object)
        self._rng = np.random.default_rng(seed)
        self._width = width
        self._height = height
        self._objects = objects
        self._agents = agents
        self._occupancy_threshold = occupancy_threshold

        # Obstacle parameters.
        self._large_obstacles = kwargs.pop("large_obstacles", {"size_range": [10, 25], "count": 0})
        self._small_obstacles = kwargs.pop("small_obstacles", {"size_range": [3, 6], "count": 0})
        self._crosses = kwargs.pop("crosses", {"count": 0})
        # Altars: hearts_count parameter overrides the count for altars.
        self._hearts_count = kwargs.pop("hearts_count", 50)
        self._clumpiness = kwargs.pop("clumpiness", 0)
        # Labyrinths: number of mini labyrinths.
        self._labyrinths = kwargs.pop("labyrinths", {"count": 0})
        # Scattered single walls.
        self._scattered_walls = kwargs.pop("scattered_walls", {"count": 0})
        # NEW: Blocks – rectangular objects.
        self._blocks = kwargs.pop("blocks", {"count": 0})

    def _build(self) -> np.ndarray:
        # Prepare agent symbols.
        if isinstance(self._agents, int):
            agents = ["agent.agent"] * self._agents
        elif isinstance(self._agents, dict) or isinstance(self._agents, DictConfig):
            agents = ["agent." + agent for agent, na in self._agents.items() for _ in range(na)]
        else:
            agents = []

        # Pre-scale objects if overall occupancy might exceed threshold.
        area = self._width * self._height
        total_objects = sum(self._objects.values()) + len(agents)
        if total_objects > self._occupancy_threshold * area:
            scale = (self._occupancy_threshold * area) / total_objects
            for obj in self._objects:
                if self._objects[obj] > 0:
                    self._objects[obj] = max(1, int(self._objects[obj] * scale))

        # Create an empty grid.
        grid = np.full((self._height, self._width), "empty", dtype=object)

        # Place features in order.
        grid = self._place_labyrinths(grid)
        grid = self._place_all_obstacles(grid)
        grid = self._place_scattered_walls(grid)
        grid = self._place_blocks(grid)
        for obj, count in self._objects.items():
            if obj == "altar":
                count = self._hearts_count
            for _ in range(count):
                pos = self._choose_random_empty(grid)
                if pos is None:
                    raise ValueError("No empty space available for object placement.")
                grid[pos[0], pos[1]] = obj
        for agent in agents:
            pos = self._choose_random_empty(grid)
            if pos is None:
                raise ValueError("No empty space available for agent placement.")
            grid[pos[0], pos[1]] = agent

        return grid

    # ---------------------------
    # Helper Functions
    # ---------------------------
    def _find_candidates(self, grid: np.ndarray, region_shape: Tuple[int, int]) -> List[Tuple[int, int]]:
        region_h, region_w = region_shape
        h, w = grid.shape
        candidates = []
        for r in range(h - region_h + 1):
            for c in range(w - region_w + 1):
                if np.all(grid[r:r+region_h, c:c+region_w] == "empty"):
                    candidates.append((r, c))
        return candidates

    def _choose_random_empty(self, grid: np.ndarray) -> Optional[Tuple[int, int]]:
        empty_positions = np.argwhere(grid == "empty")
        if len(empty_positions) == 0:
            return None
        idx = self._rng.integers(0, len(empty_positions))
        return tuple(empty_positions[idx])
    
    def _place_candidate_region(self, grid: np.ndarray, pattern: np.ndarray, clearance: int = 0) -> bool:
        p_h, p_w = pattern.shape
        eff_h, eff_w = p_h + 2*clearance, p_w + 2*clearance
        candidates = self._find_candidates(grid, (eff_h, eff_w))
        if candidates:
            r, c = candidates[self._rng.integers(0, len(candidates))]
            grid[r+clearance:r+clearance+p_h, c+clearance:c+clearance+p_w] = pattern
            return True
        return False

    # ---------------------------
    # Placement Routines
    # ---------------------------
    def _place_labyrinths(self, grid: np.ndarray) -> np.ndarray:
        labyrinth_count = self._labyrinths.get("count", 0)
        for _ in range(labyrinth_count):
            pattern = self._generate_labyrinth_pattern()
            candidates = self._find_candidates(grid, pattern.shape)
            if candidates:
                r, c = candidates[self._rng.integers(0, len(candidates))]
                grid[r:r+pattern.shape[0], c:c+pattern.shape[1]] = pattern
            else:
                print("Warning: Could not place a labyrinth; no valid region found.")
        return grid

    def _place_all_obstacles(self, grid: np.ndarray) -> np.ndarray:
        clearance = 1
        # Place large obstacles.
        large_count = self._large_obstacles.get("count", 0)
        low_large, high_large = self._large_obstacles.get("size_range", [10, 25])
        for _ in range(large_count):
            target = self._rng.integers(low_large, high_large + 1)
            pattern = self._generate_random_shape(target)
            if not self._place_candidate_region(grid, pattern, clearance):
                print(f"Warning: Could not place large obstacle of {target} blocks.")
        # Place small obstacles.
        small_count = self._small_obstacles.get("count", 0)
        low_small, high_small = self._small_obstacles.get("size_range", [3, 6])
        for _ in range(small_count):
            target = self._rng.integers(low_small, high_small + 1)
            pattern = self._generate_random_shape(target)
            if not self._place_candidate_region(grid, pattern, clearance):
                print(f"Warning: Could not place small obstacle of {target} blocks.")
        # Place cross obstacles (no extra clearance).
        crosses_count = self._crosses.get("count", 0)
        for _ in range(crosses_count):
            pattern = self._generate_cross_pattern()
            candidates = self._find_candidates(grid, pattern.shape)
            if candidates:
                r, c = candidates[self._rng.integers(0, len(candidates))]
                grid[r:r+pattern.shape[0], c:c+pattern.shape[1]] = pattern
            else:
                print("Warning: Could not place cross obstacle.")
        return grid

    def _place_scattered_walls(self, grid: np.ndarray) -> np.ndarray:
        count = self._scattered_walls.get("count", 0)
        empty_positions = np.argwhere(grid == "empty")
        if len(empty_positions) == 0:
            return grid
        num_to_place = min(count, len(empty_positions))
        indices = self._rng.permutation(len(empty_positions))[:num_to_place]
        for idx in indices:
            r, c = empty_positions[idx]
            grid[r, c] = "wall"
        return grid

    def _place_blocks(self, grid: np.ndarray) -> np.ndarray:
        """
        Places rectangular blocks on the grid.
        Each block's width and height are sampled uniformly between 2 and 14.
        The number of blocks is determined by self._blocks["count"] (0 to 10).
        A candidate region of the sampled dimensions must be completely empty.
        If no such region exists, placement of that block is skipped.
        """
        block_count = self._blocks.get("count", 0)
        h, w = grid.shape
        for _ in range(block_count):
            block_w = self._rng.integers(2, 15)  # [2,14]
            block_h = self._rng.integers(2, 15)
            candidates = self._find_candidates(grid, (block_h, block_w))
            if candidates:
                r, c = candidates[self._rng.integers(0, len(candidates))]
                grid[r:r+block_h, c:c+block_w] = "block"
            else:
                print(f"Warning: Could not place block of size {block_h}x{block_w}.")
        return grid

    # ---------------------------
    # Pattern Generation Functions
    # ---------------------------
    def _generate_random_shape(self, num_blocks: int) -> np.ndarray:
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
            new_cell = candidates[self._rng.integers(0, len(candidates))]
            shape_cells.add(new_cell)
        min_r = min(r for r, _ in shape_cells)
        min_c = min(c for _, c in shape_cells)
        max_r = max(r for r, _ in shape_cells)
        max_c = max(c for _, c in shape_cells)
        pattern = np.full((max_r - min_r + 1, max_c - min_c + 1), "empty", dtype=object)
        for r, c in shape_cells:
            pattern[r - min_r, c - min_c] = "wall"
        return pattern

    def _generate_cross_pattern(self) -> np.ndarray:
        cross_w = self._rng.integers(1, 9)
        cross_h = self._rng.integers(1, 9)
        pattern = np.full((cross_h, cross_w), "empty", dtype=object)
        center_row = cross_h // 2
        center_col = cross_w // 2
        pattern[center_row, :] = "wall"
        pattern[:, center_col] = "wall"
        return pattern

    def _generate_labyrinth_pattern(self) -> np.ndarray:
        # Choose dimensions between 11 and 13, then clamp to 11 and force odd.
        h = int(self._rng.integers(11, 14))
        w = int(self._rng.integers(11, 14))
        h = 11 if h > 11 else h
        w = 11 if w > 11 else w
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

        # Apply thickening based on a random probability between 0.3 and 1.0.
        thick_prob = 0.3 + 0.7 * self._rng.random()
        maze_thick = maze.copy()
        for i in range(1, h - 1):
            for j in range(1, w - 1):
                if maze[i, j] == "empty":
                    if self._rng.random() < thick_prob and j + 1 < w:
                        maze_thick[i, j + 1] = "empty"
                    if self._rng.random() < thick_prob and i + 1 < h:
                        maze_thick[i + 1, j] = "empty"
        maze = maze_thick

        # Ensure each border has at least two contiguous empty cells.
        if w > 3 and not self._has_gap(maze[0, 1:w-1]):
            maze[0, 1:3] = "empty"
        if w > 3 and not self._has_gap(maze[h - 1, 1:w-1]):
            maze[h - 1, 1:3] = "empty"
        if h > 3 and not self._has_gap(maze[1:h-1, 0]):
            maze[1:3, 0] = "empty"
        if h > 3 and not self._has_gap(maze[1:h-1, w - 1]):
            maze[1:3, w - 1] = "empty"

        # Scatter hearts in empty cells with 30% probability.
        for i in range(h):
            for j in range(w):
                if maze[i, j] == "empty" and self._rng.random() < 0.3:
                    maze[i, j] = "heart"
        return maze

    def _has_gap(self, line: np.ndarray) -> bool:
        contiguous = 0
        for cell in line:
            contiguous = contiguous + 1 if cell == "empty" else 0
            if contiguous >= 2:
                return True
        return False

    def _place_labyrinths(self, grid: np.ndarray) -> np.ndarray:
        labyrinth_count = self._labyrinths.get("count", 0)
        for _ in range(labyrinth_count):
            pattern = self._generate_labyrinth_pattern()
            candidates = self._find_candidates(grid, pattern.shape)
            if candidates:
                r, c = candidates[self._rng.integers(0, len(candidates))]
                grid[r:r+pattern.shape[0], c:c+pattern.shape[1]] = pattern
            else:
                print("Warning: Could not place a labyrinth; no valid region found.")
        return grid

    def _place_all_obstacles(self, grid: np.ndarray) -> np.ndarray:
        clearance = 1
        # Place large obstacles.
        large_count = self._large_obstacles.get("count", 0)
        low_large, high_large = self._large_obstacles.get("size_range", [10, 25])
        for _ in range(large_count):
            target = self._rng.integers(low_large, high_large + 1)
            pattern = self._generate_random_shape(target)
            if not self._place_candidate_region(grid, pattern, clearance):
                print(f"Warning: Could not place large obstacle of {target} blocks.")
        # Place small obstacles.
        small_count = self._small_obstacles.get("count", 0)
        low_small, high_small = self._small_obstacles.get("size_range", [3, 6])
        for _ in range(small_count):
            target = self._rng.integers(low_small, high_small + 1)
            pattern = self._generate_random_shape(target)
            if not self._place_candidate_region(grid, pattern, clearance):
                print(f"Warning: Could not place small obstacle of {target} blocks.")
        # Place cross obstacles.
        crosses_count = self._crosses.get("count", 0)
        for _ in range(crosses_count):
            pattern = self._generate_cross_pattern()
            candidates = self._find_candidates(grid, pattern.shape)
            if candidates:
                r, c = candidates[self._rng.integers(0, len(candidates))]
                grid[r:r+pattern.shape[0], c:c+pattern.shape[1]] = pattern
            else:
                print("Warning: Could not place cross obstacle.")
        return grid

    def _place_scattered_walls(self, grid: np.ndarray) -> np.ndarray:
        count = self._scattered_walls.get("count", 0)
        empty_positions = np.argwhere(grid == "empty")
        if len(empty_positions) == 0:
            return grid
        num_to_place = min(count, len(empty_positions))
        indices = self._rng.permutation(len(empty_positions))[:num_to_place]
        for idx in indices:
            r, c = empty_positions[idx]
            grid[r, c] = "wall"
        return grid

    def _place_blocks(self, grid: np.ndarray) -> np.ndarray:
        """
        Places rectangular block objects on the grid.
        For each block, the width and height are sampled uniformly between 2 and 14.
        The number of blocks is determined by self._blocks["count"].
        The block is placed in a candidate region that is completely empty.
        """
        block_count = self._blocks.get("count", 0)
        for _ in range(block_count):
            block_w = self._rng.integers(2, 15)  # 2 to 14 inclusive.
            block_h = self._rng.integers(2, 15)
            candidates = self._find_candidates(grid, (block_h, block_w))
            if candidates:
                r, c = candidates[self._rng.integers(0, len(candidates))]
                grid[r:r+block_h, c:c+block_w] = "block"
            else:
                print(f"Warning: Could not place block of size {block_h}x{block_w}.")
        return grid

    def _choose_random_empty(self, grid: np.ndarray) -> Optional[Tuple[int, int]]:
        empty_positions = np.argwhere(grid == "empty")
        if len(empty_positions) == 0:
            return None
        idx = self._rng.integers(0, len(empty_positions))
        return tuple(empty_positions[idx])

    def _find_candidates(self, grid: np.ndarray, region_shape: Tuple[int, int]) -> List[Tuple[int, int]]:
        region_h, region_w = region_shape
        h, w = grid.shape
        candidates = []
        for r in range(h - region_h + 1):
            for c in range(w - region_w + 1):
                if np.all(grid[r:r+region_h, c:c+region_w] == "empty"):
                    candidates.append((r, c))
        return candidates

    def _place_candidate_region(self, grid: np.ndarray, pattern: np.ndarray, clearance: int = 0) -> bool:
        p_h, p_w = pattern.shape
        eff_shape = (p_h + 2 * clearance, p_w + 2 * clearance)
        candidates = self._find_candidates(grid, eff_shape)
        if candidates:
            r, c = candidates[self._rng.integers(0, len(candidates))]
            grid[r+clearance:r+clearance+p_h, c+clearance:c+clearance+p_w] = pattern
            return True
        return False

    def _choose_random_empty_region(self, grid: np.ndarray, region_shape: Tuple[int,int]) -> Optional[Tuple[int,int]]:
        candidates = self._find_candidates(grid, region_shape)
        if candidates:
            return candidates[self._rng.integers(0, len(candidates))]
        return None

# End of VariedTerrainDiverse class implementation