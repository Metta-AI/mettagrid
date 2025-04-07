from typing import TypedDict
import numpy as np
import numpy.typing as npt

from .node import Node

class TypedChild(TypedDict):
    scene: 'Scene'
    select: str

# Base class for all map scenes.
class Scene:
    def __init__(self, children: list[TypedChild] = []):
        self._children = children
        pass

    def make_node(self, grid: npt.NDArray[np.str_]):
        return Node(self, grid)

    # Render does two things:
    # - updates `node.grid` as it sees fit
    # - creates areas of interest in a node through `node.make_area()`
    def _render(self, node: Node) -> None:
        raise NotImplementedError("Subclass must implement render method")

    def render(self, node: Node):
        self._render(node)

        for child in self._children:
            selector = child["select"]
            areas = node.select_areas(selector)
            for area in areas:
                child_node = child["scene"].make_node(area["grid"])
                print(type(child_node.scene))
                child_node.render()
