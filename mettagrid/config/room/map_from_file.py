import numpy as np
import os
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
        self._level = np.load(f"{self.dir}/{uri}")
        return self._level
