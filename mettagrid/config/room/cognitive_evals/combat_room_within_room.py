from typing import Set, Tuple, Union, Dict
import numpy as np
import random

from mettagrid.config.room.room import Room
from mettagrid.config.room.utils import create_grid, draw_border  # Utility functions

class RoomWithinRoom(Room):
    """
    Outer room with walls and a centered inner room (with a door gap in its top wall).
    Multi-agent version: one team starts inside the inner room and the other team starts outside.
    
    Inside the inner room:
      - A generator, a mine, and a heart altar are placed.
      
    Outside the inner room:
      - A generator and a mine are placed.
    """
    def __init__(self, width: int, height: int,
                 inner_size_min: int, inner_size_max: int,
                 inner_room_gap_min: int, inner_room_gap_max: int,
                 border_width: int = 1, border_object: str = "wall",
                 agents: Union[int, Dict[str, int]] = 1, seed=None):
        super().__init__(border_width=border_width, border_object=border_object)
        self._overall_width, self._overall_height = width, height
        self._inner_size_min, self._inner_size_max = inner_size_min, inner_size_max
        self._inner_room_gap_min, self._inner_room_gap_max = inner_room_gap_min, inner_room_gap_max
        # Handle multi-agent configuration.
        # Expect exactly two teams: the first (alphabetically) will start inside,
        # and the second will start outside.
        if isinstance(agents, int):
            inside_agents = agents // 2
            outside_agents = agents - inside_agents
            self._agents = {"team_1": inside_agents, "team_2": outside_agents}
        else:
            if len(agents) != 2:
                raise ValueError("Expected exactly 2 teams for RoomWithinRoom combat.")
            self._agents = agents
        self._total_agents = sum(self._agents.values())
        self._rng = np.random.default_rng(seed)
        self._wall_positions: Set[Tuple[int, int]] = set()
        self._border_width = border_width

        # Sample inner room dimensions.
        self._inner_width = self._rng.integers(inner_size_min, inner_size_max + 1)
        self._inner_height = self._rng.integers(inner_size_min, inner_size_max + 1)

    def _build(self) -> np.ndarray:
        grid = create_grid(self._overall_height, self._overall_width, fill_value="empty")
        bw, ow, oh = self._border_width, self._overall_width, self._overall_height

        # Draw outer walls.
        draw_border(grid, bw, self._border_object)
        self._wall_positions.update(map(tuple, np.argwhere(grid == self._border_object)))

        # Define inner room dimensions (centered).
        inner_w, inner_h = self._inner_width, self._inner_height
        left = (ow - inner_w) // 2
        top = (oh - inner_h) // 2
        right = left + inner_w - 1
        bottom = top + inner_h - 1

        # Determine door gap on the inner room's top wall.
        door_gap = int(self._rng.integers(self._inner_room_gap_min, self._inner_room_gap_max + 1))
        max_gap = inner_w - 2 * bw - 2
        door_gap = min(door_gap, max_gap) if max_gap > 0 else door_gap
        door_start = left + bw + ((inner_w - 2 * bw - door_gap) // 2)

        # Draw inner room walls.
        for x in range(left, right + 1):
            if door_start <= x < door_start + door_gap:
                grid[top, x] = "door"
            else:
                grid[top, x] = self._border_object
                self._wall_positions.add((x, top))
        for x in range(left, right + 1):
            grid[bottom, x] = self._border_object
            self._wall_positions.add((x, bottom))
        for y in range(top + 1, bottom):
            grid[y, left] = self._border_object
            grid[y, right] = self._border_object
            self._wall_positions.add((left, y))
            self._wall_positions.add((right, y))

        # Place inner room objects: generator, heart altar, and mine.
        grid[top + bw, left + bw] = "generator"
        grid[top + bw, right - bw] = "altar"
        grid[bottom - bw, right - bw] = "mine"

        # Place outer room objects (only generator and mine, no altar).
        ox, oy = bw + 1, bw + 1
        grid[oy, ox] = "generator"
        if ox + 1 < ow - bw:
            grid[oy, ox + 1] = "mine"

        # Multi-agent placement.
        # By convention, the first team (alphabetically) starts inside the inner room,
        # and the second team starts outside.
        team_keys = sorted(self._agents.keys())
        inside_team = team_keys[0]
        outside_team = team_keys[1]

        # Gather available positions inside the inner room (excluding walls and objects).
        inside_positions = []
        for y in range(top + 1, bottom):
            for x in range(left + 1, right):
                if grid[y, x] == "empty":
                    inside_positions.append((x, y))
        random.shuffle(inside_positions)
        for _ in range(self._agents[inside_team]):
            if inside_positions:
                pos = inside_positions.pop()
                grid[pos[1], pos[0]] = f"agent.{inside_team}"
            else:
                break

        # Gather available positions outside the inner room (any empty cell not in the inner room interior).
        outside_positions = []
        for y in range(oh):
            for x in range(ow):
                if grid[y, x] == "empty":
                    # Exclude positions inside the inner room's interior.
                    if not (left + 1 <= x <= right - 1 and top + 1 <= y <= bottom - 1):
                        outside_positions.append((x, y))
        random.shuffle(outside_positions)
        for _ in range(self._agents[outside_team]):
            if outside_positions:
                pos = outside_positions.pop()
                grid[pos[1], pos[0]] = f"agent.{outside_team}"
            else:
                break

        return grid
