from typing import Optional, Tuple, List
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
        occupancy_threshold: float = 0.66,  # maximum fraction of grid cells to occupy
        **kwargs  # Accept extra parameters
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
        # Altars: hearts_count overrides number of altars.
        self._hearts_count = kwargs.pop("hearts_count", 50)
        self._clumpiness = kwargs.pop("clumpiness", 0)
        # Labyrinths: count of mini labyrinths (mazes).
        self._labyrinths = kwargs.pop("labyrinths", {"count": 0})
        # Scattered single walls.
        self._scattered_walls = kwargs.pop("scattered_walls", {"count": 0})

    def _build(self) -> np.ndarray:
        # Prepare agent symbols.
        if isinstance(self._agents, int):
            agents = ["agent.agent"] * self._agents
        elif isinstance(self._agents, dict) or isinstance(self._agents, DictConfig):
            agents = ["agent." + agent for agent, na in self._agents.items() for _ in range(na)]
        else:
            agents = []

        # --- Pre-scale objects by estimated occupancy ---
        area = self._width * self._height
        total_objects = sum(self._objects.values()) + len(agents)
        if total_objects > self._occupancy_threshold * area:
            scale = (self._occupancy_threshold * area) / total_objects
            for obj in self._objects:
                if self._objects[obj] > 0:
                    # Ensure at least one instance if originally nonzero.
                    self._objects[obj] = max(1, int(self._objects[obj] * scale))

        # Create an empty grid.
        grid = np.full((self._height, self._width), "empty", dtype=object)

        # Place features in order:
        grid = self._place_labyrinths(grid)
        grid = self._place_all_obstacles(grid)
        grid = self._place_scattered_walls(grid)

        # --- Place remaining objects (e.g., altars, other objects) ---
        for obj, count in self._objects.items():
            if obj == "altar":
                count = self._hearts_count
            for _ in range(count):
                pos = self._choose_random_empty(grid)
                if pos is None:
                    raise ValueError("No empty space available for object placement.")
                grid[pos[0], pos[1]] = obj

        # --- Place agents ---
        for agent in agents:
            pos = self._choose_random_empty(grid)
            if pos is None:
                raise ValueError("No empty space available for agent placement.")
            grid[pos[0], pos[1]] = agent

        return grid

    # --------------------------------------------------------------------------
    # Helper Functions for Candidate Search and Placement
    # --------------------------------------------------------------------------
    def _find_candidates(self, grid: np.ndarray, region_shape: Tuple[int, int]) -> List[Tuple[int, int]]:
        """
        Returns list of top-left indices where a sub-region of given shape is completely "empty".
        """
        region_h, region_w = region_shape
        h, w = grid.shape
        candidates = []
        for r in range(h - region_h + 1):
            for c in range(w - region_w + 1):
                if np.all(grid[r:r+region_h, c:c+region_w] == "empty"):
                    candidates.append((r, c))
        return candidates

    def _choose_random_empty(self, grid: np.ndarray) -> Optional[Tuple[int, int]]:
        """
        Returns a random empty cell (as a tuple) from the grid.
        """
        empty_positions = np.argwhere(grid == "empty")
        if len(empty_positions) == 0:
            return None
        idx = self._rng.integers(0, len(empty_positions))
        return tuple(empty_positions[idx])

    def _place_candidate_region(self, grid: np.ndarray, pattern: np.ndarray, clearance: int = 0) -> bool:
        """
        Attempts to place a given pattern on grid. If clearance > 0, an effective region is
        computed by padding the pattern dimensions with the clearance.
        """
        p_h, p_w = pattern.shape
        effective_h, effective_w = p_h + 2 * clearance, p_w + 2 * clearance
        candidates = self._find_candidates(grid, (effective_h, effective_w))
        if candidates:
            r, c = candidates[self._rng.integers(0, len(candidates))]
            grid[r+clearance: r+clearance+p_h, c+clearance: c+clearance+p_w] = pattern
            return True
        return False

    # --------------------------------------------------------------------------
    # Placement Routines
    # --------------------------------------------------------------------------
    def _place_labyrinths(self, grid: np.ndarray) -> np.ndarray:
        """
        Place mini labyrinths onto the grid.
        """
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
        """
        Places large obstacles, small obstacles, and cross obstacles on the grid.
        For obstacles, a one-cell clearance is enforced.
        """
        clearance = 1

        # Place large obstacles.
        large_count = self._large_obstacles.get("count", 0)
        low_large, high_large = self._large_obstacles.get("size_range", [10, 25])
        for _ in range(large_count):
            target_blocks = self._rng.integers(low_large, high_large + 1)
            pattern = self._generate_random_shape(target_blocks)
            if not self._place_candidate_region(grid, pattern, clearance):
                print(f"Warning: Could not place large obstacle of {target_blocks} blocks.")

        # Place small obstacles.
        small_count = self._small_obstacles.get("count", 0)
        low_small, high_small = self._small_obstacles.get("size_range", [3, 6])
        for _ in range(small_count):
            target_blocks = self._rng.integers(low_small, high_small + 1)
            pattern = self._generate_random_shape(target_blocks)
            if not self._place_candidate_region(grid, pattern, clearance):
                print(f"Warning: Could not place small obstacle of {target_blocks} blocks.")

        # Place cross obstacles (no extra clearance assumed).
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
        """
        Scatter single wall cells randomly on empty grid locations.
        """
        count = self._scattered_walls.get("count", 0)
        empty_positions = np.argwhere(grid == "empty")
        if len(empty_positions) == 0:
            return grid
        # Randomly select indices (without replacement) for wall placement.
        num_to_place = min(count, len(empty_positions))
        indices = self._rng.permutation(len(empty_positions))[:num_to_place]
        for idx in indices:
            r, c = empty_positions[idx]
            grid[r, c] = "block"
        return grid

    # --------------------------------------------------------------------------
    # Pattern Generation Functions (unchanged in spirit)
    # --------------------------------------------------------------------------
    def _generate_random_shape(self, num_blocks: int) -> np.ndarray:
        """
        Generates a random connected shape with num_blocks cells set to "wall" using a random walk.
        The shape is normalized (top-left at (0,0)).
        """
        shape_cells = {(0, 0)}
        # Use candidate growth until desired number of blocks is reached.
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
        # Normalize shape coordinates.
        min_r = min(r for r, _ in shape_cells)
        min_c = min(c for _, c in shape_cells)
        max_r = max(r for r, _ in shape_cells)
        max_c = max(c for _, c in shape_cells)
        pattern = np.full((max_r - min_r + 1, max_c - min_c + 1), "empty", dtype=object)
        for r, c in shape_cells:
            pattern[r - min_r, c - min_c] = "wall"
        return pattern

    def _generate_cross_pattern(self) -> np.ndarray:
        """
        Generates a cross-shaped obstacle.
        Both width and height are sampled between 1 and 8 (inclusive).
        The center row and column are set to "wall".
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
        Generates a mini labyrinth (maze) pattern.
        Dimensions are chosen randomly near 11×11 and forced to be odd.
        A recursive backtracking algorithm carves passages. After that, passages
        are thickened probabilistically, border gaps are ensured, and empty cells
        are randomly replaced with "heart".
        """
        # Choose dimensions between 11 and 13 then clamp and force oddness.
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

        # Apply thickening to passages.
        thick_prob = 0.3 + 0.7 * self._rng.random()
        maze_thick = maze.copy()
        for i in range(1, h - 1):
            for j in range(1, w - 1):
                if maze[i, j] == "empty":
                    if self._rng.random() < thick_prob and j+1 < w:
                        maze_thick[i, j + 1] = "empty"
                    if self._rng.random() < thick_prob and i+1 < h:
                        maze_thick[i + 1, j] = "empty"
        maze = maze_thick

        # Ensure border gaps of at least 2 cells.
        if w > 3 and not self._has_gap(maze[0, 1:w-1]):
            maze[0, 1:3] = "empty"
        if w > 3 and not self._has_gap(maze[h - 1, 1:w-1]):
            maze[h - 1, 1:3] = "empty"
        if h > 3 and not self._has_gap(maze[1:h-1, 0]):
            maze[1:3, 0] = "empty"
        if h > 3 and not self._has_gap(maze[1:h-1, w - 1]):
            maze[1:3, w - 1] = "empty"

        # Randomly scatter hearts over empty cells with 30% probability.
        for i in range(h):
            for j in range(w):
                if maze[i, j] == "empty" and self._rng.random() < 0.3:
                    maze[i, j] = "heart"

        return maze

    def _has_gap(self, line: np.ndarray) -> bool:
        """
        Returns True if a 1D array has at least 2 contiguous "empty" cells.
        """
        contiguous = 0
        for cell in line:
            contiguous = contiguous + 1 if cell == "empty" else 0
            if contiguous >= 2:
                return True
        return False

# ==============================================================================
# End of VariedTerrainLabyrinths
# ==============================================================================
