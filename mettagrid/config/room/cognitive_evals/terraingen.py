from opensimplex import OpenSimplex
import numpy as np
from typing import NamedTuple

from mettagrid.config.room.room import Room
from mettagrid.config.room.utils import furthest, vacant_neighbors

class Layer(NamedTuple):
    fn: 'function'
    satur: float

# Capture the flag between teams ?
# Treasure hunt
# Race course
# Optimal trade routes ?
# Territory control ?
# Freeze tag
# Hide-and-seek
# Maze solving !

class TerrainGen(Room):
    """A random terrain dictated by layers of sampling functions 'fn'."""
    def __init__(self, 
                 width: int, 
                 height: int, 
                 layers: list[Layer], # layers dictate how generated noise is sampled and how the end result will look
                 scenario: str = "maze", # 
                 sampling_params: dict = {}, # additional optional non-necessary helping params, can help with creating interpolated sets of rooms
                 seed: int = 1, 
                 border_width: int = 1,
                 border_object: str = "wall", 
                 cutoff: int = 70): # cutoff that separates walls in noise from 0 to 255, bigger cuttof means more walls, usually left untouched
        super().__init__(border_width=border_width, border_object=border_object)
        self._width, self._height = width, height
        self.sampling_params = sampling_params
        self.cutoff = cutoff
        self.seed = seed
        self.layers = layers
        self.scenario = scenario

    def _build(self) -> np.ndarray:
        terrain = np.ones(shape=(self._width,self._height)) # template neutral terrain of ones to prevent errors
        for layer in self.layers:
            if abs(layer.satur) > 0.00001: terrain *= self.terrain_map(layer) # terrains layered on top of each other via multiplication,
                                                                              # terrains with ~0 saturation are skipped from calculation
        terrain = self.normalize_array(terrain) # sets min value as 0, max as 1 via appropriate rescaling
        terrain = (terrain * 255).astype('uint8')
        # add converters and stuff
        room = np.array(np.where(terrain > self.cutoff, 'empty','wall'), dtype='<U50')
        self.fix_map(room) # function that finds unconnected regions and connects them anyway, works slow, could be optimized
        
        match self.scenario:
            case "maze":
                '''
                creates maze scenario with agent, altar, converter and mine
                agent and altar are placed as far away from each other as possible
                converter and mine are placed next to altar
                '''
                space = np.where(room == 'empty')
                initial_guess = (space[0][0], space[1][0])
                furthest_point1 = furthest(initial_guess[0], initial_guess[1], room)
                assert furthest_point1 != (-1,-1), "Error: initial guess is forbidden tile"
                furthest_point2 = furthest(furthest_point1[0], furthest_point1[1], room)
                assert furthest_point1 != (-1,-1), "Error: second guess is forbidden tile"
                room[furthest_point1[0],furthest_point1[1]] = "agent.agent"
                room[furthest_point2[0],furthest_point2[1]] = 'altar'
                converter = vacant_neighbors([furthest_point2], room)
                if len(converter) > 0:
                    converter = converter.pop()
                    room[converter] = 'converter'
                else: raise ValueError("No space for converter")
                mine = vacant_neighbors([converter, furthest_point2], room)
                if len(mine) > 0:
                    mine = mine.pop()
                    room[mine] = 'mine'
                else: raise ValueError("No space for mine")
                
            case 'haul':
                '''
                creates haul scenario with agent, altar, converter and mine
                agent and altar are placed as far away from each other as possible
                converter is placed next to agent, mine is placed next to altar
                agent is expected to be able to reach altar hauling converter with him
                '''
                space = np.where(room == 'empty')
                initial_guess = (space[0][0], space[1][0])
                furthest_point1 = furthest(initial_guess[0], initial_guess[1], room)
                furthest_point2 = furthest(furthest_point1[0], furthest_point1[1], room)
                room[furthest_point1[0],furthest_point1[1]] = "agent.agent"
                room[furthest_point2[0],furthest_point2[1]] = 'altar'
                converter = vacant_neighbors([furthest_point1], room)
                if len(converter) > 0:
                    converter = converter.pop()
                    room[converter] = 'converter'
                else: raise ValueError("No space for converter")
                mine = vacant_neighbors([furthest_point2], room)
                if len(mine) > 0:
                    mine = mine.pop()
                    room[mine] = 'mine'
                else: raise ValueError("No space for mine")

        return room
    
    def normalize_array(self, room: np.ndarray) -> np.ndarray:
        norm_arr = (room - np.min(room)) / (np.max(room) - np.min(room))
        return norm_arr
    
    def terrain_map(self, layer: Layer) -> np.ndarray:
        simplex = OpenSimplex(self.seed)

        xa = np.array(range(self._width))/self._width
        ya = np.array(range(self._height))/self._height
        terrain = np.array([simplex.noise2(*layer.fn(x, y, **self.sampling_params)) for y in ya for x in xa]) # fn function dictates where and how fast noise will be sampled for each pixel in a room, absolute value is less important than derivative of this function
                                                                                                              # the faster noise is sampled: fn(x,y) ~ fn(x+1,y) in some region the less changes will be in this region per pixel, noise will look zoomed in
                                                                                                              # the slower noise is sampled: fn(x,y) !=fn(x+1,y) in some region the more changes will be in this region per pixel, noise will look zoomed out
        terrain = (terrain + 1)/2 # changes range from [-1,1] to [0,1]
        terrain = terrain.reshape((self._width,self._height))
        terrain = terrain**layer.satur # saturates pattern with walls. Helpful since base noise is balanced to be 50/50. Saturation 0 makes neutral terrain with 0 walls, saturation >100 fills everything with walls.

        return terrain
    
    def fix_map(self, room: np.ndarray) -> None:
        #find any empty cell as start
        start = np.where(room == 'empty')
        if start[0].size == 0:
            return
        start = (start[0][0],start[1][0])

        def out_of_bound(x, y):
            if x < 0 or y < 0:
                return True
            if x >= self._width or y >= self._height:
                return True
            return False
        
        dir_list = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        while True:
            closed_set = {}
            open_list_empty = [start]
            open_list_wall = []

            #find area border
            while open_list_empty:
                current = open_list_empty.pop(0)
                if room[current[0], current[1]] == 'wall':
                    open_list_wall.append(current)
                    continue
                for next_dir in dir_list:
                    next_pos = (current[0] + next_dir[0], current[1] + next_dir[1])
                    if out_of_bound(next_pos[0], next_pos[1]):
                        continue
                    if next_pos in closed_set:
                        continue
                    closed_set[next_pos] = 1
                    open_list_empty.append(next_pos)

            #find another empty area
            predecessor_map = {}
            another_empty_cell = (-1, -1)
            while open_list_wall:
                current = open_list_wall.pop(0)
                if room[current[0], current[1]] == 'empty':
                    another_empty_cell = current
                    break
                for next_dir in dir_list:
                    next_pos = (current[0] + next_dir[0], current[1] + next_dir[1])
                    if out_of_bound(next_pos[0], next_pos[1]):
                        continue
                    if next_pos in closed_set:
                        continue
                    closed_set[next_pos] = 1
                    predecessor_map[next_pos] = current
                    open_list_wall.append(next_pos)

            #cannot find another empty area, break
            if another_empty_cell == (-1, -1):
                break

            #link two empty areas
            while another_empty_cell in predecessor_map:
                predecessor = predecessor_map[another_empty_cell]
                room[predecessor[0]][predecessor[1]] = 'empty'
                another_empty_cell = predecessor
            