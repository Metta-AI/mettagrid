import pytest

from mettagrid.grid import Grid
from mettagrid.grid_object import GridLocation, GridObject, PyOrientation


@pytest.fixture
def basic_grid():
    return Grid(5, 5, [0, 0])


def test_add_and_query_cpp_object(basic_grid):
    obj = GridObject()
    obj.init(1, 1, 1, 0)

    # Save ID before adding to grid (in case the grid modifies it)
    obj_id = obj.id()

    # Add object to grid
    assert basic_grid.py_add_object(obj)

    # Get the PyGridObject - this is where segfault might occur
    py_obj = basic_grid.py_object(obj_id)

    # First just check if it exists
    assert py_obj is not None

    # Then check individual properties one by one
    assert py_obj.obj_id == obj_id
    assert py_obj.type_id == 1
    assert py_obj.row == 1
    assert py_obj.col == 1
    assert py_obj.layer == 0


def test_object_at_cpp_and_type(basic_grid):
    obj = GridObject()
    obj.init(1, 2, 2, 0)
    basic_grid.py_add_object(obj)

    loc = obj.location()
    obj_id = obj.id()

    # Our methods now return PyGridObjects
    py_obj = basic_grid.py_object_at(loc)
    assert py_obj is not None
    assert py_obj.obj_id == obj_id

    # Test with correct type
    py_obj_typed = basic_grid.py_object_at_with_type(loc, 1)
    assert py_obj_typed is not None
    assert py_obj_typed.obj_id == obj_id

    # Test with incorrect type
    assert basic_grid.py_object_at_with_type(loc, 2) is None


def test_move_object_cpp(basic_grid):
    obj = GridObject()
    obj.init(1, 1, 1, 0)
    basic_grid.py_add_object(obj)

    obj_id = obj.id()
    new_loc = GridLocation(3, 3, 0)
    assert basic_grid.py_move_object(obj_id, new_loc)

    # Verify location updated via py_get_location
    loc = basic_grid.py_get_location(obj_id)
    assert loc.py_row() == 3 and loc.py_col() == 3

    # Also verify using py_object
    py_obj = basic_grid.py_object(obj_id)
    assert py_obj.row == 3
    assert py_obj.col == 3

    # Verify object is found at new location
    at_new_loc = basic_grid.py_object_at(new_loc)
    assert at_new_loc is not None
    assert at_new_loc.obj_id == obj_id

    # And not at old location
    old_loc = GridLocation(1, 1, 0)
    assert basic_grid.py_object_at(old_loc) is None


def test_swap_objects_cpp(basic_grid):
    obj1 = GridObject()
    obj1.init(1, 1, 1, 0)
    obj2 = GridObject()
    obj2.init(1, 2, 2, 0)

    basic_grid.py_add_object(obj1)
    basic_grid.py_add_object(obj2)

    obj1_id = obj1.id()
    obj2_id = obj2.id()

    # Store original locations
    orig_loc1 = basic_grid.py_get_location(obj1_id)
    orig_loc2 = basic_grid.py_get_location(obj2_id)

    basic_grid.swap_objects(obj1_id, obj2_id)

    # Get updated objects
    py_obj1 = basic_grid.py_object(obj1_id)
    py_obj2 = basic_grid.py_object(obj2_id)

    # Verify coordinates have been swapped
    assert py_obj1.row == orig_loc2.py_row()
    assert py_obj1.col == orig_loc2.py_col()
    assert py_obj2.row == orig_loc1.py_row()
    assert py_obj2.col == orig_loc1.py_col()


def test_remove_object_cpp(basic_grid):
    obj = GridObject()
    obj.init(1, 1, 1, 0)
    basic_grid.py_add_object(obj)

    obj_id = obj.id()
    loc = obj.location()

    # Verify the object exists
    assert basic_grid.py_object(obj_id) is not None
    assert basic_grid.py_object_at(loc) is not None

    # Remove and verify it's gone
    basic_grid.py_remove_object(obj)
    assert basic_grid.py_object(obj_id) is None
    assert basic_grid.py_object_at(loc) is None


def test_remove_object_by_id_cpp(basic_grid):
    obj = GridObject()
    obj.init(1, 1, 1, 0)
    basic_grid.py_add_object(obj)

    obj_id = obj.id()
    loc = obj.location()

    # Verify the object exists
    assert basic_grid.py_object(obj_id) is not None
    assert basic_grid.py_object_at(loc) is not None

    # Remove by ID and verify it's gone
    basic_grid.remove_object_by_id(obj_id)
    assert basic_grid.py_object(obj_id) is None
    assert basic_grid.py_object_at(loc) is None


def test_is_empty_cpp(basic_grid):
    # Start with empty grid
    assert basic_grid.is_empty(0, 0)

    # Add an object at (0,0)
    obj = GridObject()
    obj.init(1, 0, 0, 0)
    basic_grid.py_add_object(obj)

    # Cell should no longer be empty
    assert not basic_grid.is_empty(0, 0)

    # Other cells should still be empty
    assert basic_grid.is_empty(1, 1)
    assert basic_grid.is_empty(4, 4)


def test_relative_locations_cpp(basic_grid):
    loc = GridLocation(2, 2, 0)

    # Test all directions
    up = basic_grid.py_relative_location(loc, PyOrientation.UP)
    down = basic_grid.py_relative_location(loc, PyOrientation.DOWN)
    left = basic_grid.py_relative_location(loc, PyOrientation.LEFT)
    right = basic_grid.py_relative_location(loc, PyOrientation.RIGHT)

    # Verify coordinates
    assert up.py_row() == 1
    assert up.py_col() == 2

    assert down.py_row() == 3
    assert down.py_col() == 2

    assert left.py_row() == 2
    assert left.py_col() == 1

    assert right.py_row() == 2
    assert right.py_col() == 3


def test_relative_location_with_type_cpp(basic_grid):
    loc = GridLocation(1, 1, 0)

    # Test with type parameter
    relative_loc = basic_grid.py_relative_location_with_type(loc, PyOrientation.RIGHT, 1)

    # Verify result is a GridLocation
    assert isinstance(relative_loc, GridLocation)

    # Verify coordinates
    assert relative_loc.py_row() == 1
    assert relative_loc.py_col() == 2
    assert relative_loc.py_layer() == 0  # Should match the layer mapping for type 1


def test_relative_location_full_cpp(basic_grid):
    loc = GridLocation(1, 1, 0)

    # Test with all parameters
    relative_loc = basic_grid.py_relative_location_full(loc, PyOrientation.DOWN, 2, 1, 0)

    # Verify result is a GridLocation
    assert isinstance(relative_loc, GridLocation)

    # Verify coordinates (DOWN direction with distance 2 and offset 1)
    assert relative_loc.py_row() == 3  # 1 + 2 (distance)
    assert relative_loc.py_col() == 2  # 1 + 1 (offset)
    assert relative_loc.py_layer() == 0  # Should match the layer for type 0


def test_grid_boundaries(basic_grid):
    """Test that relative locations are properly clamped to grid boundaries"""
    # Create a location at the edge of the grid
    edge_loc = GridLocation(0, 0, 0)

    # Try to go beyond the edge
    beyond = basic_grid.py_relative_location(edge_loc, PyOrientation.UP)

    # Should be clamped to the grid boundary
    assert beyond.py_row() == 0
    assert beyond.py_col() == 0

    # Try the other edge
    edge_loc = GridLocation(4, 4, 0)
    beyond = basic_grid.py_relative_location(edge_loc, PyOrientation.DOWN)

    # Should be clamped to the grid boundary (max size is 5x5)
    assert beyond.py_row() == 4
    assert beyond.py_col() == 4


def test_object_lifecycle(basic_grid):
    """Test a complete object lifecycle: add, move, query, remove"""
    # Create and add object
    obj = GridObject()
    obj.init(1, 1, 1, 0)
    basic_grid.py_add_object(obj)
    obj_id = obj.id()

    # Verify it's in the grid
    py_obj = basic_grid.py_object(obj_id)
    assert py_obj is not None
    assert py_obj.obj_id == obj_id

    # Verify it's at the correct location
    obj_at_loc = basic_grid.py_object_at(obj.location())
    assert obj_at_loc is not None
    assert obj_at_loc.obj_id == obj_id

    # Move to new location
    new_loc = GridLocation(3, 3, 0)
    basic_grid.py_move_object(obj_id, new_loc)

    # Verify using py_object
    moved_obj = basic_grid.py_object(obj_id)
    assert moved_obj.row == 3
    assert moved_obj.col == 3

    # Verify found at new location, not at old
    at_new_loc = basic_grid.py_object_at(new_loc)
    assert at_new_loc is not None
    assert at_new_loc.obj_id == obj_id

    assert basic_grid.py_object_at(GridLocation(1, 1, 0)) is None

    # Remove the object
    basic_grid.remove_object_by_id(obj_id)

    # Verify it's gone
    assert basic_grid.py_object(obj_id) is None
    assert basic_grid.py_object_at(new_loc) is None
    assert basic_grid.is_empty(3, 3)


def test_py_grid_object_properties(basic_grid):
    """Test that PyGridObject contains all expected properties"""
    # Create an object in the grid
    obj = GridObject()
    obj.init(1, 2, 3, 4)
    basic_grid.py_add_object(obj)

    # Retrieve as PyGridObject
    py_obj = basic_grid.py_object(obj.id())

    # Verify all properties are present and correct
    assert py_obj is not None
    assert py_obj.obj_id == obj.id()
    assert py_obj.type_id == 1
    assert py_obj.row == 2
    assert py_obj.col == 3
    assert py_obj.layer == 4
