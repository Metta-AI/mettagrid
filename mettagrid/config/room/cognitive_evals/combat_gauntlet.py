from typing import Union, Dict
import numpy as np
import random

from mettagrid.config.room.room import Room

class CombatGauntlet(Room):
    """
    A narrow combat gauntlet map where:
      - The left region contains 10 mines.
      - The right region contains 10 generators.
      - A heart altar is placed at the center.
    Agents are placed according to team: the first team (alphabetically) is placed in the left region,
    while the second team is placed in the right region.
    """
    def __init__(self, width: int, height: int,
                 agents: Union[int, Dict[str, int]] = 1,
                 border_width: int = 1, border_object: str = "wall", seed=None):
        super().__init__(border_width=border_width, border_object=border_object)
        self._width = width
        self._height = height
        # Handle multi-agent configuration:
        if isinstance(agents, int):
            # Divide equally into two teams.
            left_agents = agents // 2
            right_agents = agents - left_agents
            self._agents = {"team_1": left_agents, "team_2": right_agents}
        else:
            if len(agents) != 2:
                raise ValueError("CombatGauntlet expects exactly 2 teams.")
            self._agents = agents
        self._total_agents = sum(self._agents.values())
        self._seed = seed
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

    def _build(self) -> np.ndarray:
        # Create grid with all cells initialized as "empty"
        grid = np.full((self._height, self._width), "empty", dtype='<U50')

        # Draw border walls
        for x in range(self._width):
            grid[0, x] = self._border_object
            grid[self._height - 1, x] = self._border_object
        for y in range(self._height):
            grid[y, 0] = self._border_object
            grid[y, self._width - 1] = self._border_object

        # Define regions:
        # Left region: x in [1, left_region_max)
        # Right region: x in [right_region_min, width-1)
        left_region_max = self._width // 3
        right_region_min = 2 * self._width // 3

        # Place the heart altar at the center of the grid.
        center_x = self._width // 2
        center_y = self._height // 2
        grid[center_y, center_x] = "altar"

        # Place 10 mines in the left region.
        mines_needed = 10
        left_positions = []
        for y in range(1, self._height - 1):
            for x in range(1, left_region_max):
                if grid[y, x] == "empty":
                    left_positions.append((x, y))
        random.shuffle(left_positions)
        for _ in range(mines_needed):
            if left_positions:
                pos = left_positions.pop()
                grid[pos[1], pos[0]] = "mine"

        # Place 10 generators in the right region.
        generators_needed = 10
        right_positions = []
        for y in range(1, self._height - 1):
            for x in range(right_region_min, self._width - 1):
                if grid[y, x] == "empty":
                    right_positions.append((x, y))
        random.shuffle(right_positions)
        for _ in range(generators_needed):
            if right_positions:
                pos = right_positions.pop()
                grid[pos[1], pos[0]] = "generator"

        # Place agents according to team.
        # By convention, sort team keys: the first team is placed in the left region, the second in the right.
        team_keys = sorted(self._agents.keys())
        left_team = team_keys[0]
        right_team = team_keys[1]

        # Collect empty cells in left region for left_team agents.
        left_agent_positions = []
        for y in range(1, self._height - 1):
            for x in range(1, left_region_max):
                if grid[y, x] == "empty":
                    left_agent_positions.append((x, y))
        random.shuffle(left_agent_positions)
        for _ in range(self._agents[left_team]):
            if left_agent_positions:
                pos = left_agent_positions.pop()
                grid[pos[1], pos[0]] = f"agent.{left_team}"

        # Collect empty cells in right region for right_team agents.
        right_agent_positions = []
        for y in range(1, self._height - 1):
            for x in range(right_region_min, self._width - 1):
                if grid[y, x] == "empty":
                    right_agent_positions.append((x, y))
        random.shuffle(right_agent_positions)
        for _ in range(self._agents[right_team]):
            if right_agent_positions:
                pos = right_agent_positions.pop()
                grid[pos[1], pos[0]] = f"agent.{right_team}"

        return grid