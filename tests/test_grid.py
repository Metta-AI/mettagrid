import pytest

from mettagrid.grid import Grid
from mettagrid.grid_object import GridLocation, Orientation, TestGridObject


@pytest.fixture
def basic_grid():
    return Grid(5, 5, [0, 0])


def test_add_and_query_cpp_object(basic_grid):
    obj = TestGridObject()
    obj.init(1, 1, 1, 0)
    assert basic_grid.py_add_object(obj)  # Using py_add_object instead
    retrieved = basic_grid.py_object(obj.id())  # Using py_object instead
    assert retrieved is not None
    assert retrieved.location.row() == obj.location().row()
    assert retrieved.location.col() == obj.location().col()
    assert retrieved.location.layer() == obj.location().layer()


def test_object_at_cpp_and_type(basic_grid):
    obj = TestGridObject()
    obj.init(1, 2, 2, 0)
    basic_grid.py_add_object(obj)  # Using py_add_object instead
    loc = obj.location()
    assert basic_grid.py_object_at(loc) == obj._cpp_obj  # Using py_object_at instead
    assert basic_grid.py_object_at_with_type(loc, 1) == obj._cpp_obj  # Using py_object_at_with_type instead
    assert basic_grid.py_object_at_with_type(loc, 2) is None  # Using py_object_at_with_type instead


def test_move_object_cpp(basic_grid):
    obj = TestGridObject()
    obj.init(1, 1, 1, 0)
    basic_grid.py_add_object(obj)  # Using py_add_object instead
    new_loc = GridLocation(3, 3, 0)
    assert basic_grid.py_move_object(obj.id(), new_loc)  # Using py_move_object instead
    loc = basic_grid.py_location(obj.id())  # Using py_location instead
    assert loc.row() == 3 and loc.col() == 3


def test_swap_objects_cpp(basic_grid):
    obj1 = TestGridObject()
    obj1.init(1, 1, 1, 0)
    obj2 = TestGridObject()
    obj2.init(1, 2, 2, 0)
    basic_grid.py_add_object(obj1)  # Using py_add_object instead
    basic_grid.py_add_object(obj2)  # Using py_add_object instead
    basic_grid.swap_objects(obj1.id(), obj2.id())  # This is already cpdef, so no prefix needed
    assert basic_grid.py_location(obj1.id()).row() == 2  # Using py_location instead
    assert basic_grid.py_location(obj2.id()).row() == 1  # Using py_location instead


def test_remove_object_cpp(basic_grid):
    obj = TestGridObject()
    obj.init(1, 1, 1, 0)
    basic_grid.py_add_object(obj)  # Using py_add_object instead
    basic_grid.py_remove_object(obj)  # Using py_remove_object instead
    assert basic_grid.py_object(obj.id()) is None  # Using py_object instead


def test_remove_object_by_id_cpp(basic_grid):
    obj = TestGridObject()
    obj.init(1, 1, 1, 0)
    basic_grid.py_add_object(obj)  # Using py_add_object instead
    basic_grid.remove_object_by_id(obj.id())  # This is already cpdef, so no prefix needed
    assert basic_grid.py_object(obj.id()) is None  # Using py_object instead


def test_is_empty_cpp(basic_grid):
    assert basic_grid.is_empty(0, 0)  # This is already cpdef, so no prefix needed
    obj = TestGridObject()
    obj.init(1, 0, 0, 0)
    basic_grid.py_add_object(obj)  # Using py_add_object instead
    assert not basic_grid.is_empty(0, 0)  # This is already cpdef, so no prefix needed


def test_relative_locations_cpp(basic_grid):
    loc = GridLocation(2, 2, 0)
    up = basic_grid.py_relative_location(loc, Orientation.UP)  # Using py_relative_location instead
    down = basic_grid.py_relative_location(loc, Orientation.DOWN)  # Using py_relative_location instead
    left = basic_grid.py_relative_location(loc, Orientation.LEFT)  # Using py_relative_location instead
    right = basic_grid.py_relative_location(loc, Orientation.RIGHT)  # Using py_relative_location instead
    assert up.row() < loc.row()
    assert down.row() > loc.row()
    assert left.col() < loc.col()
    assert right.col() > loc.col()


def test_relative_location_with_type_cpp(basic_grid):
    loc = GridLocation(1, 1, 0)
    relative_loc = basic_grid.py_relative_location_with_type(
        loc, Orientation.RIGHT, 1
    )  # Using py_relative_location_with_type instead
    assert isinstance(relative_loc, GridLocation)


def test_relative_location_full_cpp(basic_grid):
    loc = GridLocation(1, 1, 0)
    relative_loc = basic_grid.py_relative_location_full(
        loc, Orientation.DOWN, 2, 1, 0
    )  # Using py_relative_location_full instead
    assert isinstance(relative_loc, GridLocation)
