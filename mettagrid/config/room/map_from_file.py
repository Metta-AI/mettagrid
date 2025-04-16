import numpy as np
import os
import random
from mettagrid.config.room.room import Room


class MapFromFile(Room):
    def __init__(self, dir, border_width: int = 0, border_object: str = "wall"):
        if not os.path.exists(dir) and os.path.exists(dir + ".zip"):
            import zipfile
            with zipfile.ZipFile(dir + ".zip", 'r') as zip_ref:
                zip_ref.extractall(os.path.dirname(dir))
        self.files = os.listdir(dir)
        self.dir = dir
        super().__init__(border_width=border_width, border_object=border_object)

    def _build(self):
        uri = np.random.choice(self.files)
        level = np.load(f"{self.dir}/{uri}")
        num_hearts = random.randint(30, 150)

        # Find valid empty spaces surrounded by empty
        valid_positions = []
        for i in range(1, level.shape[0]-1):
            for j in range(1, level.shape[1]-1):
                if self._grid[i,j] == "empty":
                    # Check if position is accessible from at least one direction
                    if (level[i-1,j] == "empty" or
                        level[i+1,j] == "empty" or
                        level[i,j-1] == "empty" or
                        level[i,j+1] == "empty"):
                        valid_positions.append((i,j))

        # Randomly place hearts in valid positions
        positions = random.sample(valid_positions, min(num_hearts, len(valid_positions)))
        for pos in positions:
            level[pos] = "altar"
        self._level = level
        return self._level
