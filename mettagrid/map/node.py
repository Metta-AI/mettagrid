import random
from typing import TypedDict
import numpy as np
import numpy.typing as npt

class Area(TypedDict):
    id: int # unique for areas in a node; not unique across nodes.
    grid: npt.NDArray[np.str_]
    tags: list[str]

# Container for a map slice, with a scene to render.
class Node:
    _areas: list[Area]

    def __init__(self, scene, grid: npt.NDArray[np.str_]):
        self.scene = scene

        # Not prefixed with `_`; scene renderers access these directly.
        self.grid = grid
        self.height = grid.shape[0]
        self.width = grid.shape[1]

        self._areas = []

        # { "lockname": [area_id1, area_id2, ...] }
        self._locks = {}

    def render(self):
        self.scene.render(self)

    def make_area(self, x: int, y: int, width: int, height: int, tags: list[str] = []) -> Area:
        area: Area = {
            "id": len(self._areas),
            "grid": self.grid[y:y+height, x:x+width],
            "tags": tags,
        }
        self._areas.append(area)
        return area

    def select_areas(self, query) -> list[Area]:
        areas = self._areas

        filtered_areas: list[Area] = []
        where = query.get("where")
        if where:
            for area in areas:
                match = True
                for tag in where["tags"]:
                    if tag not in area["tags"]:
                        match = False
                        break

                if match:
                    filtered_areas.append(area)
        else:
            filtered_areas = areas

        # Filter out locked areas.
        lock = query.get("lock")
        if lock:
            if lock not in self._locks:
                self._locks[lock] = []

            # Remove areas that are locked.
            filtered_areas = [area for area in filtered_areas if area["id"] not in self._locks[lock]]


        limit = query.get("limit")
        if limit is not None and limit < len(filtered_areas):
            order_by = query.get("order_by", "random")
            if order_by == "random":
                filtered_areas = random.sample(filtered_areas, k=limit)
            elif order_by == "first":
                filtered_areas = filtered_areas[:limit]
            elif order_by == "last":
                filtered_areas = filtered_areas[-limit:]

        if lock:
            # Add final list of used areas to the lock.
            self._locks[lock].extend([area["id"] for area in filtered_areas])

        return filtered_areas

