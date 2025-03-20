import numpy as np
from mettagrid.config.room.room import Room

class ConjoinedRooms(Room):
    """
    Constructs a contiguous grid of conjoined rooms.

    The overall map is partitioned into a 10×10 grid of rooms.
    Each room is a rectangular block of size `room_width`×`room_height`
    (excluding walls). Walls (of thickness `border_width`) separate the rooms,
    but each wall has a centrally placed gap of size `door_gap` so that the agent
    can move between adjacent rooms.

    In every room, a mine is placed at the center.
    A single agent is placed in the overall map in the first available empty cell.
    """
    def __init__(self, rows: int, cols: int, room_width: int, room_height: int,
                 door_gap: int, border_width: int = 1, seed: int = 42):
        super().__init__(border_width=border_width, border_object="wall")
        self.rows = rows
        self.cols = cols
        self.room_width = room_width
        self.room_height = room_height
        self.door_gap = door_gap
        self.border_width = border_width
        self.seed = seed

    def _build(self) -> np.ndarray:
        # Compute overall grid dimensions.
        total_height = self.rows * self.room_height + (self.rows + 1) * self.border_width
        total_width = self.cols * self.room_width + (self.cols + 1) * self.border_width

        # Start with a grid filled with "empty".
        grid = np.full((total_height, total_width), "empty", dtype='<U50')

        # Draw outer borders.
        grid[0, :] = "wall"
        grid[-1, :] = "wall"
        grid[:, 0] = "wall"
        grid[:, -1] = "wall"

        # Draw internal horizontal walls with door gaps.
        for r in range(1, self.rows):
            wall_y = r * (self.room_height + self.border_width)
            for c in range(self.cols):
                # Compute the x-range for the current room interior.
                room_start_x = c * (self.room_width + self.border_width) + self.border_width
                # Center the door gap along the room's width.
                gap_start = room_start_x + (self.room_width - self.door_gap) // 2
                gap_end = gap_start + self.door_gap
                # Fill the wall cells (within the room's horizontal extent) except for the gap.
                for x in range(room_start_x, room_start_x + self.room_width):
                    if not (gap_start <= x < gap_end):
                        grid[wall_y, x] = "wall"

        # Draw internal vertical walls with door gaps.
        for c in range(1, self.cols):
            wall_x = c * (self.room_width + self.border_width)
            for r in range(self.rows):
                room_start_y = r * (self.room_height + self.border_width) + self.border_width
                # Center the door gap along the room's height.
                gap_start = room_start_y + (self.room_height - self.door_gap) // 2
                gap_end = gap_start + self.door_gap
                for y in range(room_start_y, room_start_y + self.room_height):
                    if not (gap_start <= y < gap_end):
                        grid[y, wall_x] = "wall"

        # Place one mine in the center of each room.
        for r in range(self.rows):
            for c in range(self.cols):
                top_left_y = r * (self.room_height + self.border_width) + self.border_width
                top_left_x = c * (self.room_width + self.border_width) + self.border_width
                mine_y = top_left_y + self.room_height // 2
                mine_x = top_left_x + self.room_width // 2
                grid[mine_y, mine_x] = "mine"

        # Place the single agent in the first available empty cell.
        agent_placed = False
        for y in range(total_height):
            for x in range(total_width):
                if grid[y, x] == "empty":
                    grid[y, x] = "agent.agent"
                    agent_placed = True
                    break
            if agent_placed:
                break

        return grid