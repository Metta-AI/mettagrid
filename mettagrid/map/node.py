import numpy as np
import numpy.typing as npt

from mettagrid.map.area import Area, SelectorConfig, filter_areas

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

    def render(self):
        self.scene.render(self)

    def make_area(self, x: int, y: int, width: int, height: int, tags: list[str] = []) -> Area:
        area: Area = {
            "grid": self.grid[y:y+height, x:x+width],
            "tags": tags,
        }
        self._areas.append(area)
        return area

    def select_areas(self, selector: SelectorConfig) -> list[Area]:
        return filter_areas(selector, self._areas)
