import numpy as np
from mettagrid.config.room.room import Room

class Odyssey(Room):
    """
    Composite odyssey environment that nests several subrooms (cognitive eval maps)
    into a contiguous grid. The subrooms are arranged in a grid layout with corridors
    between them.
    """
    def __init__(self, layout: str, grid_rows: int, grid_cols: int, corridor_width: int,
                 room_builders: list, border_width: int = 1, border_object: str = "wall", seed=None):
        super().__init__(border_width=border_width, border_object=border_object)
        self.layout = layout
        self.grid_rows = grid_rows
        self.grid_cols = grid_cols
        self.corridor_width = corridor_width
        self.room_builders = room_builders
        self.seed = seed

    def _build(self) -> np.ndarray:
        # Build each subroom using its own _build() method.
        subrooms = []
        for builder in self.room_builders:
            # Assume that the builder is an already-instantiated room.
            subrooms.append(builder._build())

        # Arrange subrooms in a grid.
        # First, group the subroom grids by row.
        rows = []
        index = 0
        for r in range(self.grid_rows):
            row_rooms = subrooms[index:index+self.grid_cols]
            index += self.grid_cols
            # Determine the maximum height for the rooms in this row.
            max_height = max(room.shape[0] for room in row_rooms)
            rows.append((row_rooms, max_height))

        # For each column, compute the maximum width among the rooms in that column.
        col_widths = []
        for c in range(self.grid_cols):
            widths = []
            for r in range(self.grid_rows):
                room = subrooms[r*self.grid_cols + c]
                widths.append(room.shape[1])
            col_widths.append(max(widths))
        
        # Determine overall composite dimensions.
        total_height = sum(row_height for (_, row_height) in rows) + (self.grid_rows - 1) * self.corridor_width
        total_width = sum(col_width for col_width in col_widths) + (self.grid_cols - 1) * self.corridor_width
        
        # Initialize composite grid with "empty" cells.
        composite = np.full((total_height, total_width), "empty", dtype='<U50')
        
        # Copy each subroom grid into the appropriate location.
        current_y = 0
        for r, (row_rooms, row_height) in enumerate(rows):
            current_x = 0
            for c, room in enumerate(row_rooms):
                room_h, room_w = room.shape
                # Paste the room grid into the composite at (current_y, current_x).
                composite[current_y:current_y+room_h, current_x:current_x+room_w] = room
                current_x += col_widths[c] + self.corridor_width
            current_y += row_height + self.corridor_width

        return composite
