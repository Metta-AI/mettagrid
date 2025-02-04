import random
import numpy as np

from mettagrid.config.room.room import Room

def make_odd(x):
    if x % 2 == 0:
        x += 1
    return x

def set_position(x, uppper_bound):
    """move within bounds, ensuring that the position is odd"""
    x = make_odd(x)
    if x < 0:
        x = 1
    elif x >= uppper_bound:
        if x % 2 == 0:
            x = uppper_bound - 1
        else:
            x = uppper_bound - 2
    return x


class Maze(Room):
    EMPTY, WALL = "empty", "wall"
    START, END = "agent.agent", "altar"
    NORTH, SOUTH, EAST, WEST = 'n', 's', 'e', 'w'

    def __init__(self, width, height, start_pos, end_pos, branching, seed=None, border_width=0, border_object="wall"):
        super().__init__(border_width=border_width, border_object=border_object)
        self._width = width
        self._height = height
        self._start_pos = start_pos
        self._end_pos = end_pos
        self._branching = branching
        self._rng = random.Random(seed)

        # Validate branching parameter
        assert 0 <= self._branching <= 1, "Branching parameter must be between 0 and 1"

        # Compute an effective maze size that is odd.
        self.eff_width = self._width if self._width % 2 == 1 else self._width - 1
        self.eff_height = self._height if self._height % 2 == 1 else self._height - 1

        # The start and end positions must be odd and within the effective maze dimensions.
        self._start_pos = (set_position(self._start_pos[0], self.eff_width), set_position(self._start_pos[1], self.eff_height))
        self._end_pos = (set_position(self._end_pos[0], self.eff_width), set_position(self._end_pos[1], self.eff_height))

    def _build(self):
        """
        Generate a maze and return it as a numpy array of characters,
        matching the format from build_map_from_ascii.
        The maze is generated on an effective grid of odd dimensions (self.eff_width x self.eff_height)
        and then copied into a container of size (self._width x self._height) with extra wall rows/columns.
        """

        # Generate the effective maze using the computed odd dimensions.
        maze_eff = np.full((self.eff_height, self.eff_width), self.WALL, dtype='<U50')

        def should_branch():
            return self._rng.random() < self._branching

        def get_preferred_direction(x, y, target_x, target_y):
            if abs(target_x - x) > abs(target_y - y):
                return self.EAST if target_x > x else self.WEST
            return self.SOUTH if target_y > y else self.NORTH

        def visit(x, y, has_visited, target_x=None, target_y=None):
            maze_eff[y, x] = self.EMPTY
            while True:
                unvisited_neighbors = []
                if y > 1 and (x, y - 2) not in has_visited:
                    unvisited_neighbors.append(self.NORTH)
                if y < self.eff_height - 2 and (x, y + 2) not in has_visited:
                    unvisited_neighbors.append(self.SOUTH)
                if x > 1 and (x - 2, y) not in has_visited:
                    unvisited_neighbors.append(self.WEST)
                if x < self.eff_width - 2 and (x + 2, y) not in has_visited:
                    unvisited_neighbors.append(self.EAST)

                if not unvisited_neighbors:
                    return

                # If a target is provided and we are not branching,
                # try to move in the preferred direction.
                if target_x is not None and target_y is not None and not should_branch():
                    preferred = get_preferred_direction(x, y, target_x, target_y)
                    if preferred in unvisited_neighbors:
                        next_direction = preferred
                    else:
                        next_direction = self._rng.choice(unvisited_neighbors)
                else:
                    next_direction = self._rng.choice(unvisited_neighbors)

                next_x, next_y = x, y
                if next_direction == self.NORTH:
                    next_x, next_y = x, y - 2
                    maze_eff[y - 1, x] = self.EMPTY
                elif next_direction == self.SOUTH:
                    next_x, next_y = x, y + 2
                    maze_eff[y + 1, x] = self.EMPTY
                elif next_direction == self.WEST:
                    next_x, next_y = x - 2, y
                    maze_eff[y, x - 1] = self.EMPTY
                elif next_direction == self.EAST:
                    next_x, next_y = x + 2, y
                    maze_eff[y, x + 1] = self.EMPTY

                # Optionally create a branch by clearing an alternate neighbor.
                if should_branch() and len(unvisited_neighbors) > 1:
                    alt_directions = [d for d in unvisited_neighbors if d != next_direction]
                    alt_direction = self._rng.choice(alt_directions)
                    if alt_direction == self.NORTH:
                        maze_eff[y - 1, x] = self.EMPTY
                    elif alt_direction == self.SOUTH:
                        maze_eff[y + 1, x] = self.EMPTY
                    elif alt_direction == self.WEST:
                        maze_eff[y, x - 1] = self.EMPTY
                    elif alt_direction == self.EAST:
                        maze_eff[y, x + 1] = self.EMPTY

                has_visited.append((next_x, next_y))
                visit(next_x, next_y, has_visited,
                      target_x=target_x,
                      target_y=target_y)

        # Start the maze generation from the start position.
        has_visited = [self._start_pos]
        visit(self._start_pos[0], self._start_pos[1], has_visited,
              target_x=self._end_pos[0] if self._end_pos else None,
              target_y=self._end_pos[1] if self._end_pos else None)

        # Mark start and end positions in the effective maze.
        maze_eff[self._start_pos[1], self._start_pos[0]] = self.START
        if self._end_pos:
            maze_eff[self._end_pos[1], self._end_pos[0]] = self.END

        # Create the final maze with the full container dimensions,
        # initially filled with walls.
        final_maze = np.full((self._height, self._width), self.WALL, dtype='<U50')
        # Copy the effective maze into the top-left corner of the container.
        final_maze[:self.eff_height, :self.eff_width] = maze_eff

        return final_maze
