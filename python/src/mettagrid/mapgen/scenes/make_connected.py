import logging
from collections import deque

import numpy as np
from scipy import ndimage

from mettagrid.mapgen.scene import Scene, SceneConfig

DIRECTIONS = ((-1, 0), (0, 1), (1, 0), (0, -1))
# 4-connectivity structure for scipy.ndimage.label
STRUCTURE_4_CONNECTED = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]])

# Cost ratio for wall vs empty. Higher = prefer corridors more aggressively.
# With ratio 10, walking 10 empty cells equals digging through 1 wall.
WALL_COST_RATIO = 10
# Cost ratio for objects vs empty. Objects are more expensive to remove than walls
# because they represent placed game content, but must be removable as a last resort
# to ensure map connectivity.
OBJECT_COST_RATIO = 50

logger = logging.getLogger(__name__)


Cell = tuple[int, int]


class MakeConnectedConfig(SceneConfig):
    pass


class MakeConnected(Scene[MakeConnectedConfig]):
    """
    This scene makes the map connected by digging minimal tunnels.

    Uses weighted shortest-path to find paths that:
    - Prefer traversing existing corridors (low cost)
    - Only dig through walls when necessary (high cost)
    - Punch through at the thinnest wall sections

    Optionally balances corner distances so all corners are roughly equidistant
    from the map center (useful for fair multiplayer spawns).

    Algorithm: Dial's algorithm with bucket queues - O(n * K) where K = WALL_COST_RATIO.
    For typical grids this is effectively O(n), much faster than heap-based Dijkstra.
    """

    def render(self):
        height, width = self.grid.shape
        empty = self.grid == "empty"
        wall = self.grid == "wall"

        # === Phase 1: Ensure connectivity ===
        labels: np.ndarray
        labels, num = ndimage.label(empty, structure=STRUCTURE_4_CONNECTED)  # type: ignore[misc]
        if num > 1:
            self._connect_components(labels, num, empty, wall, height, width)

    def _connect_components(
        self, labels: np.ndarray, num: int, empty: np.ndarray, wall: np.ndarray, height: int, width: int
    ) -> None:
        """Connect all components to the largest one via minimal tunnels."""
        # Find the largest component (labels are 1-based in scipy)
        counts = np.bincount(labels.ravel())
        counts[0] = 0  # ignore background
        largest_id = int(np.argmax(counts))

        logger.debug(f"Found {num} components, largest is {largest_id}")

        # Compute weighted distances from largest component
        distances, predecessors = self._weighted_distances(labels == largest_id, empty, wall, height, width)

        # Connect each non-largest component
        logger.debug(f"Connecting {num} components")
        for component_id in range(1, num + 1):
            if component_id == largest_id:
                continue

            # Get cells of this component
            comp_ys, comp_xs = np.where(labels == component_id)

            # Find the cell with minimum weighted distance to largest component
            comp_distances = distances[comp_ys, comp_xs]
            min_idx = int(np.argmin(comp_distances))
            start_y, start_x = int(comp_ys[min_idx]), int(comp_xs[min_idx])

            self._dig_path(start_y, start_x, predecessors, wall, empty)

        # Verify connectivity
        _, num_final = ndimage.label(self.grid == "empty", structure=STRUCTURE_4_CONNECTED)  # type: ignore[misc]
        assert num_final == 1, "Map must end up with a single connected component"

    def _weighted_distances(
        self, source_mask: np.ndarray, empty: np.ndarray, wall: np.ndarray, height: int, width: int
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Dial's algorithm: bucket-based shortest path for integer edge weights.

        Three cost levels:
        - Empty cells: cost 1 (walk through)
        - Wall cells: cost K (dig through)
        - Object cells: cost J (remove as last resort, strongly avoided)

        Returns:
            distances: 2D int array of minimum cost to reach each cell
            predecessors: 2D array of (prev_y * width + prev_x), -1 for sources
        """
        K = WALL_COST_RATIO
        J = OBJECT_COST_RATIO
        INF = height * width * J + 1

        distances = np.full((height, width), INF, dtype=np.int32)
        predecessors = np.full((height, width), -1, dtype=np.int32)

        num_buckets = J + 1
        buckets: list[deque[tuple[int, int]]] = [deque() for _ in range(num_buckets)]

        source_ys, source_xs = np.where(source_mask)
        for i in range(len(source_ys)):
            y, x = int(source_ys[i]), int(source_xs[i])
            distances[y, x] = 0
            predecessors[y, x] = -2
            buckets[0].append((y, x))

        current_cost = 0
        processed = 0
        total_cells = height * width

        while processed < total_cells:
            bucket_idx = current_cost % num_buckets
            bucket = buckets[bucket_idx]

            if not bucket:
                current_cost += 1
                if current_cost > INF:
                    break
                continue

            y, x = bucket.popleft()

            if distances[y, x] < current_cost:
                continue

            processed += 1

            for dy, dx in DIRECTIONS:
                ny, nx = y + dy, x + dx
                if 0 <= ny < height and 0 <= nx < width:
                    if empty[ny, nx]:
                        step_cost = 1
                    elif wall[ny, nx]:
                        step_cost = K
                    else:
                        step_cost = J
                    new_cost = current_cost + step_cost

                    if new_cost < distances[ny, nx]:
                        distances[ny, nx] = new_cost
                        predecessors[ny, nx] = y * width + x
                        buckets[new_cost % num_buckets].append((ny, nx))

        return distances, predecessors

    def _dig_path(
        self, start_y: int, start_x: int, predecessors: np.ndarray, wall: np.ndarray, empty: np.ndarray
    ) -> None:
        """
        Trace path from start back to the largest component, digging through
        walls and removing objects as needed to ensure connectivity.
        """
        width = predecessors.shape[1]
        y, x = start_y, start_x

        while predecessors[y, x] >= 0:  # -2 = source, -1 = unvisited
            if not empty[y, x]:
                self.grid[y, x] = "empty"

            prev_flat = predecessors[y, x]
            y, x = prev_flat // width, prev_flat % width
