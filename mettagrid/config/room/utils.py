# maze_utils.py

from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import math
import random
from queue import Queue

def create_grid(height: int, width: int, fill_value: str = "empty", dtype: str = "<U50") -> np.ndarray:
    """
    Creates a NumPy grid with the given height and width, pre-filled with the specified fill_value.
    """
    return np.full((height, width), fill_value, dtype=dtype)


def draw_border(grid: np.ndarray, border_width: int, border_object: str) -> None:
    """
    Draws a border on the given grid in-place. The border (of thickness border_width) is set to border_object.
    """
    grid[:border_width, :] = border_object
    grid[-border_width:, :] = border_object
    grid[:, :border_width] = border_object
    grid[:, -border_width:] = border_object


def bresenham_line(x0: int, y0: int, x1: int, y1: int) -> List[Tuple[int, int]]:
    """
    Generate points on a line from (x0, y0) to (x1, y1) using Bresenham's algorithm.
    Returns a list of (x, y) tuples along the line.
    """
    points = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    x, y = x0, y0

    if dx > dy:
        err = dx / 2.0
        while x != x1:
            points.append((x, y))
            err -= dy
            if err < 0:
                y += sy
                err += dx
            x += sx
    else:
        err = dy / 2.0
        while y != y1:
            points.append((x, y))
            err -= dx
            if err < 0:
                x += sx
                err += dy
            y += sy
    points.append((x1, y1))
    return points


def compute_positions(start: int, end: int, blocks: List[Tuple[str, int]]) -> Dict[str, int]:
    """
    Given a starting and ending coordinate along an axis and a list of blocks (name, width),
    compute and return a dictionary mapping each block name to its starting coordinate.

    This is useful for laying out consecutive blocks with evenly distributed gaps.
    """
    total_blocks = sum(width for _, width in blocks)
    total_gap = (end - start) - total_blocks
    num_gaps = len(blocks) - 1
    base_gap = total_gap // num_gaps if num_gaps > 0 else 0
    extra = total_gap % num_gaps if num_gaps > 0 else 0

    positions = {}
    pos = start
    for i, (name, width) in enumerate(blocks):
        positions[name] = pos
        pos += width
        if i < len(blocks) - 1:
            pos += base_gap + (1 if i < extra else 0)
    return positions


def sample_position(
    x_min: int,
    x_max: int,
    y_min: int,
    y_max: int,
    min_distance: int,
    existing: List[Tuple[int, int]],
    forbidden: Optional[Set[Tuple[int, int]]] = None,
    rng: Optional[np.random.Generator] = None,
    attempts: int = 100,
) -> Tuple[int, int]:
    """
    Samples and returns a position (x, y) within the rectangular region defined by
    [x_min, x_max] and [y_min, y_max]. The position will be at least min_distance (Manhattan)
    away from all positions in the 'existing' list and not in the 'forbidden' set.

    If no valid position is found within the given number of attempts, (x_min, y_min) is returned.
    """
    if rng is None:
        rng = np.random.default_rng()
    if forbidden is None:
        forbidden = set()

    for _ in range(attempts):
        x = int(rng.integers(x_min, x_max + 1))
        y = int(rng.integers(y_min, y_max + 1))
        pos = (x, y)
        if pos in forbidden:
            continue
        if all(abs(x - ex) + abs(y - ey) >= min_distance for ex, ey in existing):
            return pos
    return (x_min, y_min)


def make_odd(x):
    return x if x % 2 == 1 else x + 1


def set_position(x, upper_bound):
    x = make_odd(x)
    if x < 0:
        return 1
    if x >= upper_bound:
        return upper_bound - 1 if x % 2 == 0 else upper_bound - 2
    return x

def furthest(x: int, y: int, grid: np.ndarray, forbidden_tile: str = "wall") -> tuple:
    '''
    Finds the furthest point in a grid from initial point (x,y), returns (-1,-1) if initial point is forbidden to traverse
    '''
    if grid[x,y] == forbidden_tile: return (-1,-1)

    open_tiles = Queue()
    open_tiles.put((x, y))
    explored = set()
    directions = [(-1,0),(1,0),(0,-1),(0,1)]

    def outside(x: int,y: int, grid: np.ndarray) -> bool:
        if x<0 or y<0 or x>=grid.shape[0] or y>=grid.shape[1]: return True
        return False
    
    furthest_point = (-1, -1)
    while not open_tiles.empty():
        current = open_tiles.get()
        if current in explored:
            continue
        explored.add(current)
        furthest_point = current

        for dx, dy in directions:
            nx, ny = current[0] + dx, current[1] + dy
            if outside(nx, ny, grid) or (nx, ny) in explored:
                continue
            if grid[nx, ny] != forbidden_tile:
                open_tiles.put((nx, ny))
                

    return furthest_point

def vacant_neighbors(points: List[Tuple[int,int]], grid: np.ndarray) -> Set[Tuple[int, int]]:
    """
    Returns a list of neighboring coordinates (up, down, left, right) for the given (x, y) position in the grid.
    """
    neighbors = set()
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    for x, y in points:
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if 0 <= nx < grid.shape[0] and 0 <= ny < grid.shape[1]:
                if grid[nx, ny] == "empty":
                    neighbors.add((nx, ny))
    return neighbors
    