from typing import Set, Tuple, Union, Dict
import numpy as np
import random
from omegaconf import DictConfig

from mettagrid.config.room.room import Room

class Cylinder(Room):
    def __init__(self, width: int, height: int, cylinder_params: DictConfig,
                 agents: Union[int, Dict[str, int]] = 1, border_width: int = 1, border_object: str = "wall"):
        super().__init__(border_width=border_width, border_object=border_object)
        self._width = width
        self._height = height
        self._cylinder_params = cylinder_params
        # If agents is given as an int, we assume a single team named "agent".
        if isinstance(agents, int):
            self._agents = {"agent": agents}
        else:
            self._agents = agents
        self._total_agents = sum(self._agents.values())
        assert cylinder_params['length'] >= 3, "Cylinder length must be at least 3"

    def _build(self) -> np.ndarray:
        self._grid = np.full((self._height, self._width), "empty", dtype='<U50')
        self._cylinder_positions = set()
        if self._cylinder_params.horizontal:
            self.place_horizontal_cylinder()
        else:
            self.place_vertical_cylinder()
        valid_positions = {
            (x, y) for x in range(1, self._width - 1)
            for y in range(1, self._height - 1)
            if (x, y) not in self._cylinder_positions
        }
        return self._place_elements(valid_positions)

    def place_horizontal_cylinder(self) -> None:
        center_y = self._height // 2
        wall_length = self._cylinder_params['length']
        start_x = (self._width - wall_length) // 2

        # Create the horizontal walls for the cylinder
        for x in range(start_x, start_x + wall_length):
            if not self._cylinder_params['both_ends'] or (x != start_x and x != start_x + wall_length - 1):
                self._grid[center_y - 1, x] = "wall"
                self._grid[center_y + 1, x] = "wall"
                self._cylinder_positions.update({(x, center_y - 1), (x, center_y + 1)})

        # Place a mine in the center of the cylinder wall
        mine_x = start_x + wall_length // 2
        self._grid[center_y, mine_x] = "mine"
        self._cylinder_positions.add((mine_x, center_y))

        # Place agents along the top of the cylinder (above the wall)
        agent_start_x = start_x + (wall_length - self._total_agents) // 2
        current_x = agent_start_x
        for team, count in self._agents.items():
            for _ in range(count):
                self._grid[center_y - 2, current_x] = f"agent.{team}"
                self._cylinder_positions.add((current_x, center_y - 2))
                current_x += 1

    def place_vertical_cylinder(self) -> None:
        center_x = self._width // 2
        wall_length = self._cylinder_params['length']
        start_y = (self._height - wall_length) // 2

        # Create the vertical walls for the cylinder
        for y in range(start_y, start_y + wall_length):
            if not self._cylinder_params['both_ends'] or (y != start_y and y != start_y + wall_length - 1):
                self._grid[y, center_x - 1] = "wall"
                self._grid[y, center_x + 1] = "wall"
                self._cylinder_positions.update({(center_x - 1, y), (center_x + 1, y)})

        # Place a mine in the center of the cylinder wall
        mine_y = start_y + wall_length // 2
        self._grid[mine_y, center_x] = "mine"
        self._cylinder_positions.add((center_x, mine_y))

        # Place agents along the left side of the cylinder (to the left of the wall)
        agent_start_y = start_y + (wall_length - self._total_agents) // 2
        current_y = agent_start_y
        for team, count in self._agents.items():
            for _ in range(count):
                self._grid[current_y, center_x - 2] = f"agent.{team}"
                self._cylinder_positions.add((center_x - 2, current_y))
                current_y += 1

    def _place_elements(self, valid_positions: Set[Tuple[int, int]]) -> np.ndarray:
        new_grid = self._grid.copy()
        # Place the heart altar at the center of the grid (inside the cylinder)
        center_x = self._width // 2
        center_y = self._height // 2
        new_grid[center_y, center_x] = "altar"

        # Ensure the center position is not reused
        if (center_x, center_y) in valid_positions:
            valid_positions.remove((center_x, center_y))

        # Place additional mines and converters (generators) in random valid positions.
        valid_list = list(valid_positions - self._cylinder_positions)
        random.shuffle(valid_list)
        extra_mines = 2      # Adjust this value as needed
        extra_generators = 2  # Adjust this value as needed

        for _ in range(extra_mines):
            if valid_list:
                pos = valid_list.pop()
                new_grid[pos[1], pos[0]] = "mine"
                self._cylinder_positions.add(pos)
        for _ in range(extra_generators):
            if valid_list:
                pos = valid_list.pop()
                new_grid[pos[1], pos[0]] = "generator"
                self._cylinder_positions.add(pos)
        return new_grid
