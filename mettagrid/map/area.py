import random
from typing import TypedDict, Union
import numpy as np
import numpy.typing as npt
from omegaconf import DictConfig


SelectorConfig = Union[str, DictConfig]

class Area(TypedDict):
    grid: npt.NDArray[np.str_]
    tags: list[str]


def filter_areas(selector: SelectorConfig, areas: list[Area]) -> list[Area]:
    if selector == 'all':
        return areas
    elif isinstance(selector, str):
        raise ValueError(f"Unsupported selector: {selector}")

    tags = selector.tags

    filtered_areas: list[Area] = []
    for area in areas:
        match = True
        for tag in tags:
            if tag not in area["tags"]:
                match = False
                break

        if match:
            filtered_areas.append(area)

    take = selector.get("take")
    if take is not None:
        take_mode = take.get("mode", "random")
        take_count = take["count"]
        if take_mode == "random":
            filtered_areas = random.sample(filtered_areas, k=take_count)
        elif take_mode == "first":
            filtered_areas = filtered_areas[:take_count]
        elif take_mode == "last":
            filtered_areas = filtered_areas[-take_count:]

    return filtered_areas
