import math
import random
from typing import Any, Literal, Tuple, Union

import numpy as np
from mettagrid.map.node import Node
from mettagrid.map.scene import Scene

Direction = Literal["horizontal", "vertical"]

def random_divide(size: int):
    min_size = size // 3
    return random.randint(min_size, size - min_size)

class Zone:
    def __init__(self, x: int, y: int, width: int, height: int):
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def split(self) -> Tuple['Zone', 'Zone']:
        # Split in random direction, unless the room is too wide or too tall.
        if self.width > self.height * 2:
            # Note: vertical split means vertical line, not vertical layout
            direction = "vertical"
        elif self.height > self.width * 2:
            direction = "horizontal"
        else:
            direction = random.choice(["horizontal", "vertical"])

        if direction == "horizontal":
            return self.horizontal_split()
        else:
            return self.vertical_split()

    def horizontal_split(self) -> Tuple['Zone', 'Zone']:
        first_height = random_divide(self.height)
        return (
            Zone(self.x, self.y, self.width, first_height),
            Zone(self.x, self.y + first_height, self.width, self.height - first_height))

    def vertical_split(self) -> Tuple['Zone', 'Zone']:
        (child1, child2) = self.transpose().horizontal_split()
        return (child1.transpose(), child2.transpose())

    def make_room(self, min_size: int = 3, min_size_ratio: float = 0.4, max_size_ratio: float = 0.8) -> 'Zone':
        # Randomly determine room size
        def random_size(n: int) -> int:
            return random.randint(max(min_size, int(n * min_size_ratio)), max(min_size, int(n * max_size_ratio)))

        room_width = random_size(self.width)
        room_height = random_size(self.height)
        
        # Randomly position the room within the zone; always leave a 1 cell border on bottom-right, otherwise the rooms could touch each other.
        shift_x = random.randint(1, max(1, self.width - room_width))
        shift_y = random.randint(1, max(1, self.height - room_height))
        return Zone(self.x + shift_x, self.y + shift_y, room_width, room_height)

    def transpose(self) -> 'Zone':
        return Zone(self.y, self.x, self.height, self.width)

    def __repr__(self):
        return f"Zone({self.x}, {self.y}, {self.width}, {self.height})"


class Surface:
    """
    When choosing how to connect rooms, or rooms with corridors, we need to represent the surface of possible attachment points.

    Surface example:

    │#.........##│
    │###......###│
    │###......###│
    │############│
    │############│
    └────────────┘

    In this example, the surface is the set of . characters that can be approached from below (side="down").

    The empty areas on the left and right are not part of the surface.

    The code that uses the surface doesn't care what the surface is made of, it just needs to know which that can be approached.
    """

    def __init__(self, min_x: int, ys: list[int], side: Literal["up", "down"]):
        self.min_x = min_x
        self.ys = ys
        self.side = side

    @property
    def max_y(self) -> int:
        return max(self.ys)

    @property
    def min_y(self) -> int:
        return min(self.ys)

    @property
    def max_x(self) -> int:
        # Last column of the surface
        return self.min_x + len(self.ys) - 1

    def random_position(self) -> Tuple[int, int]:
        # Choose a position from which we can draw a vertical corridor.
        valid_xs = []

        def behind(y1, y2) -> bool:
            if self.side == "up":
                return y1 > y2
            else:
                return y1 < y2

        for (i, y) in enumerate(self.ys):
            # We want to exclude the columns where the vertical line would be adjacent to the surface.
            if i > 0 and behind(y, self.ys[i - 1]):
                continue
            if i < len(self.ys) - 1 and behind(y, self.ys[i + 1]):
                continue

            valid_xs.append(i)

        x = random.choice(valid_xs)
        return (x + self.min_x, self.ys[x])

    @staticmethod
    def from_zone(grid: np.ndarray, zone: Zone, side: Literal["up", "down"]) -> 'Surface':
        # Scan the entire zone, starting from the top or bottom, and collect all the y values that are part of the surface.
        min_x = None
        ys: list[int] = []

        for x in range(zone.x, zone.x + zone.width):
            yrange = range(zone.y, zone.y + zone.height)
            if side == "up":
                yrange = reversed(yrange)

            y_value = None
            for y in yrange:
                if grid[y, x] == "empty":
                    y_value = y
                    break

            if y_value is None:
                # haven't started or already ended?
                if min_x is None:
                    # ok, haven't started
                    continue
                else:
                    # we're done
                    # TODO - assert that there are no breaks in the surface?
                    break
            else:
                if min_x is None:
                    min_x = x
                ys.append(y_value)

        if min_x is None:
            raise ValueError("No surface found")

        return Surface(min_x, ys, side)

    def __repr__(self):
        return f"Surface(min_x={self.min_x}, ys={self.ys})"


class Line:
    def __init__(self, direction: Direction, start: Tuple[int, int], length: int):
        self.direction = direction

        if length < 0:
            # line of negative length means that the line is reversed (right to left or down to up)
            length = -length
            if direction == "horizontal":
                start = (start[0] - length + 1, start[1])
            else:
                start = (start[0], start[1] - length + 1)

        self.start = start
        self.length = length

    def transpose(self) -> 'Line':
        direction = "horizontal" if self.direction == "vertical" else "vertical"
        return Line(direction, (self.start[1], self.start[0]), self.length)

    def __repr__(self):
        return f"Line({self.direction}, {self.start}, {self.length})"


def connect_surfaces(surface1: Surface, surface2: Surface):
    """
    Connect two surfaces with a corridor.

    Assumes that the surfaces are adjacent and the surface1 is strictly above of surface2, i.e. all its positions are strictly smaller than all of surface2's positions.

    Example:
    ┌────────────┐
    │#........###│
    │###......###│
    │############│
    │############│
    │####.......#│
    └────────────┘

    Top set of . characters is the surface1, the bottom set is surface2.
    """

    start = surface1.random_position()
    end = surface2.random_position()

    turn_y = random.randint(surface1.max_y, surface2.min_y)

    lines = [
        # Note: off-by-one errors here were quite annoying, be careful.
        Line("vertical", start, turn_y - start[1] + 1),
        Line("horizontal", (start[0], turn_y), end[0] - start[0]),
        Line("vertical", end, turn_y - end[1] - 1),
    ]
    return lines


def connect_rooms(room1: Zone, room2: Zone):
    """
    Connect two rooms with a corridor.

    Assumes that the rooms are adjacent and the room1 is above of room2.
    """

    start = (room1.x + random.randrange(room1.width), room1.y + room1.height)
    end = (room2.x + random.randrange(room2.width), room2.y - 1)

    turn_y = random.randint(start[1], end[1])

    lines = [
        # Note: off-by-one errors here were quite annoying, be careful.
        Line("vertical", start, turn_y - start[1] + 1),
        Line("horizontal", (start[0], turn_y), end[0] - start[0]),
        Line("vertical", end, turn_y - end[1] - 1),
    ]
    return lines

class BSP(Scene):
    def __init__(self, rooms: int, min_room_size: int = 3, min_room_size_ratio: float = 0.4, max_room_size_ratio: float = 0.8, children: list[Any] = []):
        super().__init__(children=children)
        self._rooms = rooms
        self._min_room_size = min_room_size
        self._min_room_size_ratio = min_room_size_ratio
        self._max_room_size_ratio = max_room_size_ratio

    def _render(self, node: Node):
        grid = node.grid

        grid[:] = "wall"

        next_split_id = 0
        
        # Store the tree as flat list:
        # [
        #   layer1,
        #   layer2, layer2,
        #   layer3, layer3, layer3, layer3,
        #   ...
        # ]
        zones = [Zone(0, 0, grid.shape[1], grid.shape[0])]

        for _ in range(self._rooms - 1): # split rooms-1 times
            zone = zones[next_split_id]

            (child1, child2) = zone.split()
            if random.random() < 0.5:
                child1, child2 = child2, child1

            zones.append(child1)
            zones.append(child2)
            next_split_id += 1

        # make room for all zones, but only the leaf zones will be used
        rooms: list[Zone | None] = [None] * len(zones)

        # Make rooms at leaf zones
        for i in range(next_split_id, len(zones)):
            zone = zones[i]
            room = zone.make_room(self._min_room_size, self._min_room_size_ratio, self._max_room_size_ratio)
            rooms[i] = room

            grid[room.y:room.y+room.height, room.x:room.x+room.width] = "empty"
            node.make_area(room.x, room.y, room.width, room.height, tags=["room"])

        # Make corridors
        for i in range(len(zones) - 2, 0, -2):
            zone1 = zones[i]
            zone2 = zones[i + 1]

            corridor_direction = "vertical" if zone1.x == zone2.x else "horizontal"

            used_grid = grid
            if corridor_direction == "horizontal":
                used_grid = np.transpose(grid)
                zone1 = zone1.transpose()
                zone2 = zone2.transpose()

            if zone1.y > zone2.y:
                (zone1, zone2) = (zone2, zone1)

            surface1 = Surface.from_zone(used_grid, zone1, "up")
            surface2 = Surface.from_zone(used_grid, zone2, "down")

            lines = connect_surfaces(surface1, surface2)

            if corridor_direction == "horizontal":
                lines = [line.transpose() for line in lines]

            # draw lines on the original grid
            for line in lines:
                if line.direction == "vertical":
                    grid[line.start[1]:line.start[1]+line.length, line.start[0]] = "empty"
                else:
                    grid[line.start[1], line.start[0]:line.start[0]+line.length] = "empty"

            # room1 = rooms[i]
            # room2 = rooms[i + 1]

            # if room1 is None or room2 is None:
            #     continue # TODO

            # assert room1 and room2
            

            # transposed = False
            # if corridor_direction == "horizontal":
            #     room1 = room1.transpose()
            #     room2 = room2.transpose()
            #     transposed = True

            # if room1.y > room2.y:
            #     (room1, room2) = (room2, room1)

            # lines = connect_rooms(room1, room2)

            # for line in lines:
            #     if transposed:
            #         line = line.transpose()

            #     if line.direction == "vertical":
            #         grid[line.start[1]:line.start[1]+line.length, line.start[0]] = "empty"
            #     else:
            #         grid[line.start[1], line.start[0]:line.start[0]+line.length] = "empty"
