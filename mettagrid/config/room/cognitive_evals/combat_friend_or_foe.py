from typing import Union, Dict
import numpy as np
import random

from mettagrid.config.room.room import Room

class CombatFriendOrFoe(Room):
    """
    A long thin room where:
      - The left end has a single mine.
      - The right end has a single generator.
      - A heart altar is placed at the center.
      - Agents are placed on each end: team_1 on the left and team_2 on the right.
      
    The number of agents per side is customizable via the YAML.
    """
    def __init__(self, width: int, height: int,
                 agents: Union[int, Dict[str, int]] = 1,
                 border_width: int = 1, border_object: str = "wall", seed=None):
        super().__init__(border_width=border_width, border_object=border_object)
        self._width = width
        self._height = height
        # Accept agents as an int (split equally) or as a dict of two teams.
        if isinstance(agents, int):
            left_agents = agents // 2
            right_agents = agents - left_agents
            self._agents = {"team_1": left_agents, "team_2": right_agents}
        else:
            if len(agents) != 2:
                raise ValueError("CombatFriendOrFoe expects exactly 2 teams.")
            self._agents = agents
        self._total_agents = sum(self._agents.values())
        self._seed = seed
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
            
    def _build(self) -> np.ndarray:
        # Create the grid and fill with "empty".
        grid = np.full((self._height, self._width), "empty", dtype='<U50')
        
        # Draw border walls.
        for x in range(self._width):
            grid[0, x] = self._border_object
            grid[self._height - 1, x] = self._border_object
        for y in range(self._height):
            grid[y, 0] = self._border_object
            grid[y, self._width - 1] = self._border_object
        
        # Define regions:
        # Left region: x in [1, width//3)
        # Right region: x in [2*width//3, width-1)
        left_region_max = self._width // 3
        right_region_min = 2 * self._width // 3
        
        # Place static objects:
        # Place a single mine at the left end (centered vertically).
        mine_x = self._border_width + 1
        mine_y = self._height // 2
        grid[mine_y, mine_x] = "mine"
        
        # Place a single generator at the right end (centered vertically).
        generator_x = self._width - self._border_width - 2
        generator_y = self._height // 2
        grid[generator_y, generator_x] = "generator"
        
        # Place a heart altar at the center of the grid.
        center_x = self._width // 2
        center_y = self._height // 2
        grid[center_y, center_x] = "altar"
        
        # Place agents:
        # By convention, team_1 agents are placed on the left end and team_2 agents on the right end.
        team_keys = sorted(self._agents.keys())
        left_team = team_keys[0]
        right_team = team_keys[1]
        
        # Collect empty positions in the left region.
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
        
        # Collect empty positions in the right region.
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