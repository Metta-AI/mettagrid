from typing import List, Optional, Tuple

import numpy as np

from mettagrid.config.room.room import Room


class _DSU:
    """Simple disjoint‑set union (union–find) for connectivity guarantees."""

    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: int, y: int) -> bool:
        xr, yr = self.find(x), self.find(y)
        if xr == yr:
            return False
        if self.rank[xr] < self.rank[yr]:
            xr, yr = yr, xr
        self.parent[yr] = xr
        if self.rank[xr] == self.rank[yr]:
            self.rank[xr] += 1
        return True


class LatticeWorld(Room):
    """A lattice of square rooms with guaranteed connectivity and door‑density control."""

    def __init__(
        self,
        rooms_per_dim: Optional[int] = None,
        room_size: Optional[int] = None,
        heart_altar_rate: float = 0.75,
        minimum_door_rate: float = 0.75,
        num_agents: int = 0,
        border_width: int = 1,
        border_object: str = "wall",
        seed: Optional[int] = None,
    ):
        if not (0.0 <= minimum_door_rate <= 1.0):
            raise ValueError("minimum_door_rate must be between 0 and 1")
        super().__init__(border_width=border_width, border_object=border_object)

        self.seed = seed
        self.rng = np.random.default_rng(seed)

        # Random sampling of dimensions if unspecified
        self.rooms_per_dim = rooms_per_dim or int(self.rng.integers(6, 10))
        self.room_size = room_size or int(self.rng.integers(7, 13))

        self.heart_altar_rate = heart_altar_rate
        self.minimum_door_rate = minimum_door_rate
        self.num_agents = num_agents
        self.border_width = border_width
        self.border_object = border_object
        # Book‑keeping
        self.agent_positions: dict[int, Tuple[int, int]] = {}

    # ---------------------------------------------------------------------
    # Grid construction helpers
    # ---------------------------------------------------------------------
    def _build(self) -> np.ndarray:
        self.grid_size = self.rooms_per_dim * self.room_size + (self.rooms_per_dim - 1) * self.border_width
        self.grid = np.full((self.grid_size, self.grid_size), self.border_object, dtype=object)

        self._carve_rooms()
        self._carve_doors_connected()
        self._place_objects()
        return self.grid

    # ------------------------------------------------------------------
    # Room carving
    # ------------------------------------------------------------------
    def _room_bounds(self, i: int, j: int) -> Tuple[int, int, int, int]:
        row_start = i * (self.room_size + self.border_width)
        col_start = j * (self.room_size + self.border_width)
        return (
            row_start,
            row_start + self.room_size,
            col_start,
            col_start + self.room_size,
        )

    def _carve_rooms(self) -> None:
        for i in range(self.rooms_per_dim):
            for j in range(self.rooms_per_dim):
                rs, re, cs, ce = self._room_bounds(i, j)
                self.grid[rs:re, cs:ce] = "empty"

    # ------------------------------------------------------------------
    # Door carving with connectivity + density guarantee
    # ------------------------------------------------------------------
    def _carve_doors_connected(self) -> None:
        n = self.rooms_per_dim
        total_edges = 2 * n * (n - 1)
        dsu = _DSU(n * n)

        # All potential neighbour pairs
        edges: List[Tuple[int, int, str]] = []
        for i in range(n):
            for j in range(n):
                idx = i * n + j
                if j < n - 1:  # east
                    edges.append((idx, idx + 1, "E"))
                if i < n - 1:  # south
                    edges.append((idx, idx + n, "S"))
        self.rng.shuffle(edges)

        opened: set[Tuple[int, int]] = set()

        def _open(i1: int, j1: int, i2: int, j2: int) -> None:
            """Cut a centred doorway in the wall between (i1,j1) and (i2,j2)."""
            if i1 == i2:  # horizontal wall (east–west neighbour)
                rs, _, cs1, ce1 = self._room_bounds(i1, j1)
                row = rs + self.room_size // 2
                for b in range(self.border_width):
                    self.grid[row, ce1 + b] = "empty"
            else:  # vertical wall (north–south neighbour)
                _, re1, cs, _ = self._room_bounds(i1, j1)
                col = cs + self.room_size // 2
                for b in range(self.border_width):
                    self.grid[re1 + b, col] = "empty"

        # 1. Spanning tree for connectivity
        remaining_edges = []
        for a, b, _ in edges:
            if dsu.union(a, b):
                i1, j1 = divmod(a, n)
                i2, j2 = divmod(b, n)
                _open(i1, j1, i2, j2)
                opened.add(tuple(sorted((a, b))))
            else:
                remaining_edges.append((a, b))

        # 2. Extra doors until density target reached
        self.rng.shuffle(remaining_edges)
        needed = int(np.ceil(self.minimum_door_rate * total_edges))
        while len(opened) < needed and remaining_edges:
            a, b = remaining_edges.pop()
            if tuple(sorted((a, b))) in opened:
                continue
            i1, j1 = divmod(a, n)
            i2, j2 = divmod(b, n)
            _open(i1, j1, i2, j2)
            opened.add(tuple(sorted((a, b))))

    # ------------------------------------------------------------------
    # Empty‑cell helpers
    # ------------------------------------------------------------------
    def _random_empty(self) -> Tuple[int, int]:
        empties = np.argwhere(self.grid == "empty")
        if empties.size == 0:
            raise ValueError("No empty positions available")
        return tuple(int(x) for x in empties[self.rng.integers(len(empties))])

    def _random_empty_in_room(self, i: int, j: int) -> Tuple[int, int]:
        rs, _, cs, _ = self._room_bounds(i, j)
        while True:
            r = rs + int(self.rng.integers(0, self.room_size))
            c = cs + int(self.rng.integers(0, self.room_size))
            if self.grid[r, c] == "empty":
                return (r, c)

    # ------------------------------------------------------------------
    # Object placement
    # ------------------------------------------------------------------
    def _place_objects(self) -> None:
        n = self.rooms_per_dim
        all_rooms = [(i, j) for i in range(n) for j in range(n)]

        # Heart altars
        heart_rooms = [room for room in all_rooms if self.rng.random() < self.heart_altar_rate]
        for i, j in heart_rooms:
            r, c = self._random_empty_in_room(i, j)
            self.grid[r, c] = "altar"

        # Agents
        if self.num_agents > 0:
            if self.num_agents > len(all_rooms):
                raise ValueError("More agents than rooms available")
            agent_rooms = self.rng.choice(all_rooms, size=self.num_agents, replace=False)
            for idx, (i, j) in enumerate(agent_rooms):
                r, c = self._random_empty_in_room(i, j)
                self.grid[r, c] = "agent.agent"
                self.agent_positions[idx] = (r, c)
