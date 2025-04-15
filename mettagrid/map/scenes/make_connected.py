import logging
import random
from typing import Any, Tuple, Union

import numpy as np
from mettagrid.map.node import Node
from mettagrid.map.scene import Scene

directions = [(-1, 0), (0, 1), (1, 0), (0, -1)]

logger = logging.getLogger(__name__)


class MakeConnected(Scene):
    """
    This scene makes the map connected by digging tunnels.

    It does this by:
    - Finding all the connected components
    - Digging shortest tunnels from the largest component to all other components

    TODO: This can result in some extra tunnels being dug.
    """

    def __init__(self, seed=None, children: list[Any] = []):
        super().__init__(children=children)
        self._rng = random.Random(seed)

    def _render(self, node: Node):
        height, width = node.grid.shape

        component_cells = self._make_components(node)
        component_sizes = [len(cells) for cells in component_cells]

        if len(component_sizes) == 1:
            logger.debug("Map is already connected")
            return

        # find the largest component
        largest_component_id = max(
            range(len(component_sizes)), key=component_sizes.__getitem__
        )
        logger.debug(f"Largest component: {largest_component_id}")

        logger.debug("Populating distance to largest component")
        distances_to_largest_component = self._distance_to_component(
            node,
            component_cells[largest_component_id],
        )

        # connect the largest component all other components
        logger.info(f"Connecting {len(component_sizes)} components")
        for component_id, component in enumerate(component_cells):
            if component_id == largest_component_id:
                continue

            # find the cell that's closest to the largest component
            min_distance = np.inf
            min_distance_cell: Union[Tuple[int, int], None] = None
            for cell in component:
                if distances_to_largest_component[cell[0], cell[1]] < min_distance:
                    min_distance = distances_to_largest_component[cell[0], cell[1]]
                    min_distance_cell = cell

            # shouldn't happen
            if min_distance_cell is None:
                raise ValueError("No cell found for component")

            # connect the cell to the largest component by digging a tunnel based on the shortest path
            current_cell = min_distance_cell
            while distances_to_largest_component[current_cell[0], current_cell[1]] > 0:
                # Find the neighbor with the smallest distance to the largest component
                y, x = current_cell
                # Find all neighbors with the smallest distance to the largest component
                candidates = []
                min_neighbor_distance = np.inf

                for dy, dx in directions:
                    ny, nx = y + dy, x + dx
                    if ny < 0 or ny >= height or nx < 0 or nx >= width:
                        continue
                    distance = distances_to_largest_component[ny, nx]
                    if distance < min_neighbor_distance:
                        min_neighbor_distance = distance
                        candidates = [(ny, nx)]
                    elif distance == min_neighbor_distance:
                        candidates.append((ny, nx))

                # Pick a random candidate from those with the minimum distance
                if candidates:
                    next_cell = self._rng.choice(candidates)
                    node.grid[current_cell[0], current_cell[1]] = "empty"
                    current_cell = next_cell
                else:
                    # This shouldn't happen if distances are calculated correctly
                    raise ValueError("No next cell found")

    def _make_components(self, node: Node):
        # run BFS from each empty cell, find connected components
        height, width = node.grid.shape

        components = np.full((height, width), -1)
        component_id = 0
        components_cells = []

        logger.debug("Finding components")
        for y in range(height):
            for x in range(width):
                if node.grid[y, x] == "wall":
                    continue

                # already visited
                if components[y, x] != -1:
                    continue

                components_cells.append([])
                queue = [(y, x)]
                i = 0
                while i < len(queue):
                    y, x = queue[i]
                    i += 1
                    if components[y, x] != -1:
                        continue

                    components[y, x] = component_id
                    components_cells[component_id].append((y, x))

                    for dy, dx in directions:
                        ny, nx = y + dy, x + dx
                        if (
                            0 <= ny < height
                            and 0 <= nx < width
                            and node.grid[ny, nx] != "wall"
                            and components[ny, nx] == -1
                        ):
                            queue.append((ny, nx))

                component_id += 1

        logger.debug(f"Found {len(components_cells)} components")
        return components_cells

    def _distance_to_component(
        self,
        node: Node,
        component_cells: list[Tuple[int, int]],
    ):
        height, width = node.grid.shape
        # find the distance from the component to all other cells (ignoring the walls - used for finding the optimal tunnels)
        distances = np.full((height, width), np.inf)
        queue = []
        for cell in component_cells:
            distances[cell[0], cell[1]] = 0
            queue.append(cell)

        i = 0
        while i < len(queue):
            y, x = queue[i]
            i += 1

            for dy, dx in directions:
                ny, nx = y + dy, x + dx
                if 0 <= ny < height and 0 <= nx < width and distances[ny, nx] == np.inf:
                    distances[ny, nx] = distances[y, x] + 1
                    queue.append((ny, nx))

        return distances
