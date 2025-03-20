import numpy as np
import random
from mettagrid.config.room.room import Room
from mettagrid.config.room.utils import create_grid

class CombatCorridor(Room):
    """
    A combat corridor maze featuring:
      - A vertical corridor with horizontal arms.
      - The top arms (as specified by num_heart_altars) hold altars.
      - The remaining arms hold a randomized mix of generators and mines.
      - Two teams: team_1 spawns in the top half (near the altar arms)
        and team_2 in the bottom half.
    """
    def __init__(self, width: int, height: int, border_width: int = 1,
                 corridor_width: int = 2, arm_length: int = 10,
                 num_generators: int = 0, num_mines: int = 0, num_heart_altars: int = 0,
                 seed=None, agents: int = 1, rotate: bool = False, **kwargs):
        super().__init__(border_width=border_width, border_object="wall")
        self.width = width
        self.height = height
        self.border_width = border_width
        self.corridor_width = corridor_width
        self.arm_length = arm_length
        self.num_generators = num_generators
        self.num_mines = num_mines
        self.num_heart_altars = num_heart_altars
        # Total arms equals the sum of altar arms and resource arms.
        self.num_arms = self.num_heart_altars + self.num_generators + self.num_mines
        self.seed = seed
        self.agents = agents
        self.rotate = rotate
        self._rng = np.random.default_rng(seed)

    def _build(self) -> np.ndarray:
        # Create a grid filled with walls.
        grid = create_grid(self.height, self.width, fill_value="wall")
        mid_x = self.width // 2

        # Carve the vertical corridor.
        v_left = mid_x - (self.corridor_width // 2)
        v_right = v_left + self.corridor_width - 1
        grid[:, v_left:v_right+1] = "empty"

        # Evenly space arm positions along the corridor.
        spacing = (self.height - 2 * self.border_width) / (self.num_arms + 1)
        arm_y_positions = [int(self.border_width + (i + 1) * spacing) for i in range(self.num_arms)]
        # Arms remain in order from top to bottom.
        # Alternate arm directions: left for even-index arms, right for odd-index arms.
        directions = ["left" if i % 2 == 0 else "right" for i in range(self.num_arms)]

        # Assign resources to arms.
        # The top num_heart_altars arms get altars.
        remaining_arms = self.num_arms - self.num_heart_altars
        pool = (["generator"] * self.num_generators) + (["mine"] * self.num_mines)
        if len(pool) < remaining_arms:
            pool += ["empty"] * (remaining_arms - len(pool))
        else:
            pool = pool[:remaining_arms]
        self._rng.shuffle(pool)
        resource_list = ["altar"] * self.num_heart_altars + pool

        # Carve each horizontal arm and place its resource.
        for i, arm_y in enumerate(arm_y_positions):
            arm_top = arm_y - (self.corridor_width // 2)
            arm_bottom = arm_top + self.corridor_width - 1
            if directions[i] == "left":
                start_x = v_left
                end_x = max(self.border_width, start_x - self.arm_length)
                grid[arm_top:arm_bottom+1, end_x:start_x] = "empty"
                grid[arm_y, end_x] = resource_list[i]
            else:
                start_x = v_right
                end_x = min(self.width - self.border_width - 1, start_x + self.arm_length)
                grid[arm_top:arm_bottom+1, start_x+1:end_x+1] = "empty"
                grid[arm_y, end_x] = resource_list[i]

        # Agent placement:
        # Divide the maze horizontally: team_1 in the top half and team_2 in the bottom half.
        mid_y = self.height // 2
        if isinstance(self.agents, int):
            top_agents = self.agents // 2
            bottom_agents = self.agents - top_agents
            teams = {"team_1": top_agents, "team_2": bottom_agents}
        else:
            teams = self.agents

        top_positions = []
        for y in range(self.border_width, mid_y):
            for x in range(self.border_width, self.width - self.border_width):
                if grid[y, x] == "empty":
                    top_positions.append((x, y))
        random.shuffle(top_positions)
        for _ in range(teams["team_1"]):
            if top_positions:
                pos = top_positions.pop()
                grid[pos[1], pos[0]] = "agent.team_1"

        bottom_positions = []
        for y in range(mid_y, self.height - self.border_width):
            for x in range(self.border_width, self.width - self.border_width):
                if grid[y, x] == "empty":
                    bottom_positions.append((x, y))
        random.shuffle(bottom_positions)
        for _ in range(teams["team_2"]):
            if bottom_positions:
                pos = bottom_positions.pop()
                grid[pos[1], pos[0]] = "agent.team_2"

        if self.rotate:
            grid = np.rot90(grid)
        return grid