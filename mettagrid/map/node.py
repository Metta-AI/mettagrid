from typing import TypedDict
import numpy as np
import numpy.typing as npt

class Area(TypedDict):
    grid: npt.NDArray[np.str_]
    tags: list[str]

# Container for a map slice, with a scene to render.
class Node:
    def __init__(self, scene: 'Scene', grid: npt.NDArray[np.str_]):
        self.scene = scene
        self.grid = grid
        self.height = grid.shape[0]
        self.width = grid.shape[1]
        self._areas = []

    def render(self):
        self.scene.render(self)

    def replace(self, new_grid: npt.NDArray[np.str_]):
        assert new_grid.shape == self.grid.shape, f"New grid shape {new_grid.shape} does not match current grid shape {self.grid.shape}"

        self.grid[...] = new_grid

    def make_area(self, x: int, y: int, width: int, height: int, tags: list[str] = []) -> Area:
        area: Area = {
            'grid': self.grid[y:y+height, x:x+width],
            'tags': tags,
        }
        self._areas.append(area)
        return area

    def select_areas(self, selector: str) -> list[Area]:
        if selector == 'all':
            return self._areas
        else:
            # TODO - tags, etc.
            raise ValueError(f"Unsupported selector: {selector}")
