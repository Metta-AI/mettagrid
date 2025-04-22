import pytest

from mettagrid.grid import Grid
from mettagrid.grid_object import GridLocation, Orientation, TestGridObject


@pytest.fixture
def basic_grid():
    return Grid(5, 5, [0, 0])


# ------------------------
# ✅ Cython Interface Tests
# ------------------------


def test_add_and_query_cpp_object(basic_grid):
    obj = TestGridObject()
    obj.init(1, 1, 1, 0)
    assert basic_grid.add_object(obj._cpp_obj)

    retrieved = basic_grid.object(obj.id())
    assert retrieved is not None
    assert retrieved.location.row() == obj.location().row()
    assert retrieved.location.col() == obj.location().col()
    assert retrieved.location.layer() == obj.location().layer()


def test_object_at_cpp_and_type(basic_grid):
    obj = TestGridObject()
    obj.init(1, 2, 2, 0)
    basic_grid.add_object(obj._cpp_obj)
    loc = obj.location()._cpp_loc
    assert basic_grid.object_at(loc) == obj._cpp_obj
    assert basic_grid.object_at_with_type(loc, 1) == obj._cpp_obj
    assert basic_grid.object_at_with_type(loc, 2) is None


def test_move_object_cpp(basic_grid):
    obj = TestGridObject()
    obj.init(1, 1, 1, 0)
    basic_grid.add_object(obj._cpp_obj)
    new_loc = GridLocation(3, 3, 0)._cpp_loc
    assert basic_grid.move_object(obj.id(), new_loc)
    loc = basic_grid.location(obj.id())
    assert loc.row() == 3 and loc.col() == 3


def test_swap_objects_cpp(basic_grid):
    obj1 = TestGridObject()
    obj1.init(1, 1, 1, 0)
    obj2 = TestGridObject()
    obj2.init(1, 2, 2, 0)
    basic_grid.add_object(obj1._cpp_obj)
    basic_grid.add_object(obj2._cpp_obj)
    basic_grid.swap_objects(obj1.id(), obj2.id())
    assert basic_grid.location(obj1.id()).row() == 2
    assert basic_grid.location(obj2.id()).row() == 1


def test_remove_object_cpp(basic_grid):
    obj = TestGridObject()
    obj.init(1, 1, 1, 0)
    basic_grid.add_object(obj._cpp_obj)
    basic_grid.remove_object(obj._cpp_obj)
    assert basic_grid.object(obj.id()) is None


def test_remove_object_by_id_cpp(basic_grid):
    obj = TestGridObject()
    obj.init(1, 1, 1, 0)
    basic_grid.add_object(obj._cpp_obj)
    basic_grid.remove_object_by_id(obj.id())
    assert basic_grid.object(obj.id()) is None


def test_is_empty_cpp(basic_grid):
    assert basic_grid.is_empty(0, 0)
    obj = TestGridObject()
    obj.init(1, 0, 0, 0)
    basic_grid.add_object(obj._cpp_obj)
    assert not basic_grid.is_empty(0, 0)


def test_relative_locations_cpp(basic_grid):
    loc = GridLocation(2, 2, 0)._cpp_loc
    up = basic_grid.relative_location(loc, Orientation.UP)
    down = basic_grid.relative_location(loc, Orientation.DOWN)
    left = basic_grid.relative_location(loc, Orientation.LEFT)
    right = basic_grid.relative_location(loc, Orientation.RIGHT)

    assert up.row() < loc.row()
    assert down.row() > loc.row()
    assert left.col() < loc.col()
    assert right.col() > loc.col()


def test_relative_location_with_type_cpp(basic_grid):
    loc = GridLocation(1, 1, 0)._cpp_loc
    relative_loc = basic_grid.relative_location_with_type(loc, Orientation.RIGHT, 1)
    assert isinstance(relative_loc, type(loc))


def test_relative_location_full_cpp(basic_grid):
    loc = GridLocation(1, 1, 0)._cpp_loc
    relative_loc = basic_grid.relative_location_full(loc, Orientation.DOWN, 2, 1, 0)
    assert isinstance(relative_loc, type(loc))
