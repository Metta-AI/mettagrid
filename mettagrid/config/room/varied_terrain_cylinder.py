"""
VariedTerrainCylinder
---------------------
A room builder that fills the map with disjoint *cylinders*.

A *cylinder* is two parallel walls (length 4‑14) separated by a 1‑ or 2‑cell gap.
An altar sits dead‑centre in that gap. Cylinders may be vertical or horizontal.
By default they’re vertical so you can visually verify things; set
orientation="horizontal" or "random" when you like.
"""

from typing import Tuple, List, Optional
import numpy as np
from mettagrid.config.room.room import Room


class VariedTerrainCylinder(Room):
    """Scatter as many cylinders as will fit, then drop agents."""

    def __init__(
        self,
        width: int,
        height: int,
        agents: int | dict = 0,
        seed: Optional[int] = None,
        border_width: int = 0,
        border_object: str = "wall",
        orientation: str = "vertical",   # "vertical", "horizontal", or "random"
        style: str = "cylinder_world",
    ):
        super().__init__(border_width=border_width, border_object=border_object)
        self._rng = np.random.default_rng(seed)
        self._width = width
        self._height = height
        self._agents = agents
        self._orientation = orientation

        if style != "cylinder_world":
            raise ValueError(
                f"Only style 'cylinder_world' is implemented here (got '{style}')."
            )

        # Tracks which cells are busy.
        self._occupancy = np.zeros((height, width), dtype=bool)

    # ------------------------------------------------------------------ #
    # Public build
    # ------------------------------------------------------------------ #
    def _build(self) -> np.ndarray:
        grid = np.full((self._height, self._width), "empty", dtype=object)

        # 1. Scatter cylinders until no room remains.
        while True:
            pattern = self._generate_cylinder_pattern()
            if not self._place_candidate_region(grid, pattern, clearance=1):
                break

        # 2. Drop agents.
        for agent in self._make_agent_list():
            pos = self._choose_random_empty()
            if pos is None:
                break
            r, c = pos
            grid[r, c] = agent
            self._occupancy[r, c] = True

        return grid

    # ------------------------------------------------------------------ #
    # Cylinder generation
    # ------------------------------------------------------------------ #
    def _generate_cylinder_pattern(self) -> np.ndarray:
        length = int(self._rng.integers(4, 15))     # 4‑14
        gap = int(self._rng.integers(1, 3))         # 1‑2

        ori = self._orientation
        if ori == "random":
            ori = "vertical" if self._rng.random() < 0.5 else "horizontal"

        if ori == "vertical":
            h, w = length, gap + 2
            pattern = np.full((h, w), "empty", dtype=object)
            pattern[:, 0] = pattern[:, -1] = "wall"
            pattern[h // 2, 1 + gap // 2] = "altar"
        else:  # horizontal
            h, w = gap + 2, length
            pattern = np.full((h, w), "empty", dtype=object)
            pattern[0, :] = pattern[-1, :] = "wall"
            pattern[1 + gap // 2, w // 2] = "altar"

        return pattern

    # ------------------------------------------------------------------ #
    # Helpers (fast occupancy ops)
    # ------------------------------------------------------------------ #
    def _make_agent_list(self) -> List[str]:
        if isinstance(self._agents, int):
            return ["agent.agent"] * self._agents
        return [
            "agent." + name
            for name, n in self._agents.items()
            for _ in range(n)
        ]

    def _update_occupancy(self, top_left: Tuple[int, int], pattern: np.ndarray) -> None:
        r, c = top_left
        ph, pw = pattern.shape
        self._occupancy[r : r + ph, c : c + pw] |= (pattern != "empty")

    def _find_candidates(self, region_shape: Tuple[int, int]) -> List[Tuple[int, int]]:
        rh, rw = region_shape
        H, W = self._occupancy.shape
        if rh > H or rw > W:
            return []
        shape = (H - rh + 1, W - rw + 1, rh, rw)
        strides = self._occupancy.strides * 2
        sub = np.lib.stride_tricks.as_strided(self._occupancy, shape=shape, strides=strides)
        sums = sub.sum(axis=(2, 3))
        return [tuple(idx) for idx in np.argwhere(sums == 0)]

    def _place_candidate_region(
        self, grid: np.ndarray, pattern: np.ndarray, clearance: int = 0
    ) -> bool:
        ph, pw = pattern.shape
        cand = self._find_candidates((ph + 2 * clearance, pw + 2 * clearance))
        if not cand:
            return False
        r, c = cand[self._rng.integers(0, len(cand))]
        grid[r + clearance : r + clearance + ph, c + clearance : c + clearance + pw] = pattern
        self._update_occupancy((r + clearance, c + clearance), pattern)
        return True

    def _choose_random_empty(self) -> Optional[Tuple[int, int]]:
        empties = np.flatnonzero(~self._occupancy)
        if not len(empties):
            return None
        idx = self._rng.integers(0, len(empties))
        return np.unravel_index(empties[idx], self._occupancy.shape)