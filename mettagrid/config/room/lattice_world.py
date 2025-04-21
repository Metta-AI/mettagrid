from typing import Optional, Tuple

import numpy as np
from room import Room


class LatticeWorld(Room):
    """
    A world consisting of a regular lattice of square rooms, with configurable connectivity.
    Each room is a square of open space, and there may be doors in the center of each wall
    connecting to adjacent rooms based on a probability parameter.

    """

    def __init__(
        self,
        rooms_per_dim: int,
        room_size: int,
        pct_connectivity: float,
        altar_count: int,
        num_agents: int = 0,
        border_width: int = 1,
        border_object: str = "wall",
        seed: Optional[int] = None,
    ):
        super().__init__(border_width=border_width, border_object=border_object)
        self.seed = seed
        self.rng = np.random.default_rng(seed)

        self.rooms_per_dim = rooms_per_dim
        self.room_size = room_size
        self.pct_connectivity = pct_connectivity
        self.border_width = border_width
        self.border_object = border_object
        self.altar_count = altar_count
        self.num_agents = num_agents
        self.agent_positions = {}

        # Calculate the total grid size
        # Each room has room_size open space, and walls between rooms of border_width
        # We don't need to add extra border at the edges since Room handles that
        self.grid_size = rooms_per_dim * room_size + (rooms_per_dim - 1) * border_width
        self.grid = np.full((self.grid_size, self.grid_size), self.border_object)

        # Create the lattice structure
        self._create_lattice()

        # Place altars and agents
        self._place_objects()

    def _create_lattice(self):
        """Create the lattice structure with rooms and doors."""
        # First, fill the entire grid with the border object (walls)
        self.grid.fill(self.border_object)

        # Create all rooms (open spaces)
        for i in range(self.rooms_per_dim):
            for j in range(self.rooms_per_dim):
                # Calculate room boundaries
                row_start = i * (self.room_size + self.border_width)
                row_end = row_start + self.room_size
                col_start = j * (self.room_size + self.border_width)
                col_end = col_start + self.room_size

                # Open up the room space
                self.grid[row_start:row_end, col_start:col_end] = "empty"

        # Now, add doors between adjacent rooms based on connectivity probability
        for i in range(self.rooms_per_dim):
            for j in range(self.rooms_per_dim):
                # Calculate room center positions
                row_center = i * (self.room_size + self.border_width) + self.room_size // 2
                col_center = j * (self.room_size + self.border_width) + self.room_size // 2

                # Try to add a door to the right (east)
                if j < self.rooms_per_dim - 1 and self.rng.random() < self.pct_connectivity:
                    # Calculate door position
                    door_col_start = col_center + (self.room_size // 2)
                    # Create a door in the center of the wall
                    for b in range(self.border_width):
                        self.grid[row_center, door_col_start + b] = "empty"

                # Try to add a door downward (south)
                if i < self.rooms_per_dim - 1 and self.rng.random() < self.pct_connectivity:
                    # Calculate door position
                    door_row_start = row_center + (self.room_size // 2)
                    # Create a door in the center of the wall
                    for b in range(self.border_width):
                        self.grid[door_row_start + b, col_center] = "empty"

    def _random_empty(self) -> Optional[Tuple[int, int]]:
        # Create a boolean mask of empty positions
        empty_mask = self.grid == "empty"

        # Find indices of empty positions
        empties = np.flatnonzero(empty_mask)

        if empties.size == 0:
            return None

        # Select a random index
        idx = self.rng.integers(empties.size)

        # Convert flat index back to 2D coordinates
        return tuple(np.unravel_index(empties[idx], self.grid.shape))

    def _place_objects(self):
        """Place altars and agents randomly in empty spaces."""
        # Place altars first
        for _ in range(self.altar_count):
            pos = self._random_empty()
            if pos is None:
                break  # No more empty positions
            self.grid[pos] = "altar"

        # Place agents if needed
        if self.num_agents > 0:
            agent_ids = [f"agent_{i}" for i in range(self.num_agents)]
            self.agent_positions = {}

            for agent_id in agent_ids:
                pos = self._random_empty()
                if pos is None:
                    print(f"Warning: Could not place {agent_id} - no empty positions available")
                    break

                self.agent_positions[agent_id] = pos
                self.grid[pos] = agent_id  # Mark the agent in the grid
