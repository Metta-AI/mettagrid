from typing import Union, Dict
import numpy as np
import random

from mettagrid.config.room.room import Room

class CombatProtectTheGate(Room):
    """
    A long, thin combat map featuring:
      - An inner room (on the left side) with walls and a door gap.
      - A single defensive altar placed inside the inner room.
      - A gate at the far right of the overall map; its width is customizable.
      - Scattered resources in the outer arena: only mines and generators.
      
    Agent placement:
      - Team 1 (defenders) spawns inside the inner room.
      - Team 2 (attackers) spawns in the outer arena (to the right of the inner room).
    """
    def __init__(self, width: int, height: int,
                 inner_room_width: int,
                 num_scattered_mines: int,
                 num_scattered_generators: int,
                 gate_width: int = 3,
                 door_gap_height: int = 5,
                 agents: Union[int, Dict[str, int]] = 1,
                 border_width: int = 1, border_object: str = "wall", seed=None):
        super().__init__(border_width=border_width, border_object=border_object)
        self._width = width
        self._height = height
        self._inner_room_width = inner_room_width
        self._num_scattered_mines = num_scattered_mines
        self._num_scattered_generators = num_scattered_generators
        self._gate_width = gate_width
        self.door_gap_height = door_gap_height  # New parameter for door gap height.
        # Handle multi-agent configuration. Expect exactly two teams.
        if isinstance(agents, int):
            left_agents = agents // 2
            right_agents = agents - left_agents
            self._agents = {"team_1": left_agents, "team_2": right_agents}
        else:
            if len(agents) != 2:
                raise ValueError("CombatProtectTheGate expects exactly 2 teams.")
            self._agents = agents
        self._total_agents = sum(self._agents.values())
        self._seed = seed
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

    def _build(self) -> np.ndarray:
        # Create a grid filled with "empty".
        grid = np.full((self._height, self._width), "empty", dtype='<U50')
        
        # Draw outer border walls.
        for x in range(self._width):
            grid[0, x] = self._border_object
            grid[self._height - 1, x] = self._border_object
        for y in range(self._height):
            grid[y, 0] = self._border_object
            grid[y, self._width - 1] = self._border_object
        
        bw = self._border_width
        
        # Define inner room boundaries (positioned on the left side).
        inner_left = bw
        inner_top = bw
        inner_bottom = self._height - bw - 1
        inner_right = bw + self._inner_room_width - 1
        
        # Draw inner room walls.
        for x in range(inner_left, inner_right + 1):
            grid[inner_top, x] = self._border_object
            grid[inner_bottom, x] = self._border_object
        for y in range(inner_top, inner_bottom + 1):
            grid[y, inner_left] = self._border_object
            grid[y, inner_right] = self._border_object
        
        # Create a door gap in the inner room's right wall.
        available_height = inner_bottom - inner_top - 1
        gap_height = min(self.door_gap_height, available_height)
        if gap_height > 0:
            gap_start = inner_top + 1 + (available_height - gap_height) // 2
            for y in range(gap_start, gap_start + gap_height):
                grid[y, inner_right] = "door"
        
        # Place the single defensive altar inside the inner room.
        center_inner_y = (inner_top + inner_bottom) // 2
        if inner_left + 1 < inner_right:
            grid[center_inner_y, inner_left + 1] = "altar"
        
        # Place a wider gate at the far right side of the overall map.
        gate_x_start = self._width - bw - self._gate_width
        center_y = self._height // 2
        grid[center_y, gate_x_start:self._width - bw] = "gate"
        
        # Scatter resources in the outer arena (cells not inside the inner room interior).
        inner_interior = set()
        for y in range(inner_top + 1, inner_bottom):
            for x in range(inner_left + 1, inner_right):
                inner_interior.add((x, y))
                
        outer_positions = []
        for y in range(bw, self._height - bw):
            for x in range(bw, self._width - bw):
                if (x, y) not in inner_interior and grid[y, x] == "empty":
                    outer_positions.append((x, y))
        random.shuffle(outer_positions)
        
        # Scatter mines.
        for _ in range(self._num_scattered_mines):
            if outer_positions:
                pos = outer_positions.pop()
                grid[pos[1], pos[0]] = "mine"
        # Scatter generators.
        for _ in range(self._num_scattered_generators):
            if outer_positions:
                pos = outer_positions.pop()
                grid[pos[1], pos[0]] = "generator"
        
        # Place agents.
        # Convention: team_1 (defenders) spawns inside the inner room; team_2 (attackers) spawns in the outer arena.
        team_keys = sorted(self._agents.keys())
        defenders = team_keys[0]
        attackers = team_keys[1]
        
        # Collect available positions inside the inner room interior.
        inner_positions = []
        for y in range(inner_top + 1, inner_bottom):
            for x in range(inner_left + 1, inner_right):
                if grid[y, x] == "empty":
                    inner_positions.append((x, y))
        random.shuffle(inner_positions)
        for _ in range(self._agents[defenders]):
            if inner_positions:
                pos = inner_positions.pop()
                grid[pos[1], pos[0]] = f"agent.{defenders}"
        
        # Collect available positions in the outer arena (to the right of the inner room).
        outer_agent_positions = []
        for y in range(bw, self._height - bw):
            for x in range(inner_right + 1, self._width - bw):
                if grid[y, x] == "empty":
                    outer_agent_positions.append((x, y))
        random.shuffle(outer_agent_positions)
        for _ in range(self._agents[attackers]):
            if outer_agent_positions:
                pos = outer_agent_positions.pop()
                grid[pos[1], pos[0]] = f"agent.{attackers}"
        
        return grid