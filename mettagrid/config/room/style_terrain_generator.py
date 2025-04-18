# """
# style_terrain_generator.py
# ==========================
# Adds a new obstacle type—*cylinders*—to the original ``VariedTerrain``
# mechanics and introduces the style ``"cylinder_world"`` in which cylinders are
# the *only* obstacles.

# Cylinder definition
# -------------------
# • Two parallel walls of equal length (sampled uniformly 4 – 14 cells)  
# • Gap between them: 1 or 2 cells  
# • An altar centred in the gap (no other altars are spawned)  
# • Orientation chosen at random (vertical ⟷ horizontal)

# All pre‑existing styles behave exactly as before (their cylinder count is 0).
# """

from typing import Optional, Tuple, List
import numpy as np
from mettagrid.config.room.room import Room


class StyleTerrainGenerator(Room):
    # ------------------------------------------------------------------ #
    # Style parameters (original + cylinders + new cylinder_world entry)
    # ------------------------------------------------------------------ #
    STYLE_PARAMETERS = {
        # ---------- existing styles ----------
        "all-sparse": {
            "hearts_count": 25,
            "large_obstacles": {"size_range": [10, 25], "count": 2},
            "small_obstacles": {"size_range": [3, 6], "count": 2},
            "crosses": {"count": 0},
            "labyrinths": {"count": 0},
            "scattered_walls": {"count": 5},
            "blocks": {"count": 0},
            "cylinders": {"count": 0},   # new field
            "clumpiness": 0,
        },
        "balanced": {
            "hearts_count": 100,
            "large_obstacles": {"size_range": [10, 25], "count": 6},
            "small_obstacles": {"size_range": [3, 6], "count": 6},
            "crosses": {"count": 4},
            "labyrinths": {"count": 3},
            "scattered_walls": {"count": 20},
            "blocks": {"count": 3},
            "cylinders": {"count": 0},
            "clumpiness": 1,
        },
        "dense-altars-sparse-objects": {
            "hearts_count": 100,
            "large_obstacles": {"size_range": [10, 25], "count": 4},
            "small_obstacles": {"size_range": [3, 6], "count": 5},
            "crosses": {"count": 3},
            "labyrinths": {"count": 3},
            "scattered_walls": {"count": 10},
            "blocks": {"count": 3},
            "cylinders": {"count": 0},
            "clumpiness": 1,
        },
        "sparse-altars-dense-objects": {
            "hearts_count": 25,
            "large_obstacles": {"size_range": [10, 25], "count": 10},
            "small_obstacles": {"size_range": [3, 6], "count": 15},
            "crosses": {"count": 8},
            "labyrinths": {"count": 6},
            "scattered_walls": {"count": 40},
            "blocks": {"count": 5},
            "cylinders": {"count": 0},
            "clumpiness": 2,
        },
        "all-dense": {
            "hearts_count": 100,
            "large_obstacles": {"size_range": [10, 25], "count": 12},
            "small_obstacles": {"size_range": [3, 6], "count": 15},
            "crosses": {"count": 8},
            "labyrinths": {"count": 8},
            "scattered_walls": {"count": 35},
            "blocks": {"count": 8},
            "cylinders": {"count": 0},
            "clumpiness": 5,
        },
        # ---------- new style ----------
        "cylinder_world": {
            "hearts_count": 0,   # altars are inside cylinders
            "large_obstacles": {"size_range": [10, 25], "count": 0},
            "small_obstacles": {"size_range": [3, 6], "count": 0},
            "crosses": {"count": 0},
            "labyrinths": {"count": 0},
            "scattered_walls": {"count": 0},
            "blocks": {"count": 0},
            "cylinders": {"count": 999},  # ignored; we fill until no room
            "clumpiness": 0,
        },
    }

    # ------------------------------------------------------------------ #
    # Constructor
    # ------------------------------------------------------------------ #
    def __init__(
        self,
        width: int,
        height: int,
        agents: int | dict = 0,
        seed: Optional[int] = None,
        border_width: int = 0,
        border_object: str = "wall",
        style: str = "balanced",
    ):
        super().__init__(border_width=border_width, border_object=border_object)
        self._rng = np.random.default_rng(seed)
        self._width, self._height = width, height
        self._agents = agents

        if style not in self.STYLE_PARAMETERS:
            raise ValueError(f"Unknown style '{style}'")
        self._style = style
        self._params = self.STYLE_PARAMETERS[style]

        # occupancy mask: False = empty
        self._occ = np.zeros((height, width), dtype=bool)

    # ------------------------------------------------------------------ #
    # Public build
    # ------------------------------------------------------------------ #
    def _build(self) -> np.ndarray:
        if self._style == "cylinder_world":
            return self._build_cylinder_world()
        return self._build_standard()

    # ------------------------------------------------------------------ #
    # Standard build (original obstacles + cylinders if count > 0)
    # ------------------------------------------------------------------ #
    def _build_standard(self) -> np.ndarray:
        grid = np.full((self._height, self._width), "empty", dtype=object)

        # existing obstacle routines would appear here...
        grid = self._place_cylinders(grid)  # new
        grid = self._place_altars(grid)
        grid = self._place_agents(grid)
        return grid

    # ------------------------------------------------------------------ #
    # Cylinder‑only build
    # ------------------------------------------------------------------ #
    def _build_cylinder_world(self) -> np.ndarray:
        """
        Keep adding cylinders until *no* size/orientation fits anywhere.
 
        Strategy: restart the attempt with a fresh random cylinder after every
        successful placement.  Stop only after ``max_consecutive_fail`` failed
        attempts *in a row* (i.e. we tried many random sizes/orientations
        without success), which strongly suggests the map is packed.
        """
        grid = np.full((self._height, self._width), "empty", dtype=object)
        self._occ[:, :] = False
 
        max_consecutive_fail = 5
        fails = 0
        while fails < max_consecutive_fail:
            placed = self._place_cylinder_once(grid, clearance=1)
            if placed:
                fails = 0  # reset – we still found room
            else:
                fails += 1  # try a different size/orientation
 
        # Finally, spawn any requested agents on leftover empty cells
        grid = self._place_agents(grid)
        return grid

    # ------------------------------------------------------------------ #
    # Cylinder placement helpers
    # ------------------------------------------------------------------ #
    def _place_cylinders(self, grid: np.ndarray) -> np.ndarray:
        for _ in range(self._params["cylinders"]["count"]):
            self._place_cylinder_once(grid, clearance=1)
        return grid

    def _place_cylinder_once(self, grid: np.ndarray, clearance: int = 1) -> bool:
        pat = self._generate_cylinder_pattern()
        return self._place_region(grid, pat, clearance)

    def _generate_cylinder_pattern(self) -> np.ndarray:
        length = int(self._rng.integers(2, 15))
        gap = int(self._rng.integers(1, 4))
        vertical = bool(self._rng.integers(0, 2))
        if vertical:
            h, w = length, gap + 2
            pat = np.full((h, w), "empty", dtype=object)
            pat[:, 0] = pat[:, -1] = "wall"
            pat[h // 2, 1 + gap // 2] = "altar"
        else:
            h, w = gap + 2, length
            pat = np.full((h, w), "empty", dtype=object)
            pat[0, :] = pat[-1, :] = "wall"
            pat[1 + gap // 2, w // 2] = "altar"
        return pat

    # ------------------------------------------------------------------ #
    # Altars & Agents (simple versions)
    # ------------------------------------------------------------------ #
    def _place_altars(self, grid):
        for _ in range(self._params["hearts_count"]):
            pos = self._rand_empty()
            if pos:
                grid[pos] = "altar"
                self._occ[pos] = True
        return grid

    def _place_agents(self, grid):
        if isinstance(self._agents, int):
            agents = ["agent.agent"] * self._agents
        else:
            agents = ["agent." + a for a, n in self._agents.items() for _ in range(n)]
        for a in agents:
            pos = self._rand_empty()
            if pos:
                grid[pos] = a
                self._occ[pos] = True
        return grid

    # ------------------------------------------------------------------ #
    # Region placement utilities
    # ------------------------------------------------------------------ #
    def _place_region(self, grid, pattern: np.ndarray, clearance: int) -> bool:
        ph, pw = pattern.shape
        for (r, c) in self._candidate_positions((ph + 2 * clearance, pw + 2 * clearance)):
            grid[r + clearance:r + clearance + ph, c + clearance:c + clearance + pw] = pattern
            self._occ[r + clearance:r + clearance + ph, c + clearance:c + clearance + pw] |= (
                pattern != "empty"
            )
            return True
        return False

    def _candidate_positions(self, shape: Tuple[int, int]) -> List[Tuple[int, int]]:
        h, w = shape
        H, W = self._occ.shape
        if H < h or W < w:
            return []
        view_shape = (H - h + 1, W - w + 1, h, w)
        sub = np.lib.stride_tricks.as_strided(self._occ, view_shape, self._occ.strides * 2)
        sums = sub.sum(axis=(2, 3))
        coords = np.argwhere(sums == 0)
        self._rng.shuffle(coords)
        return [tuple(x) for x in coords]

    def _rand_empty(self) -> Optional[Tuple[int, int]]:
        empties = np.flatnonzero(~self._occ)
        if not len(empties):
            return None
        idx = self._rng.integers(0, len(empties))
        return tuple(np.unravel_index(empties[idx], self._occ.shape))