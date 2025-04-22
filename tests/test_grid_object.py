import numpy as np

from mettagrid.grid_object import GridLocation, Orientation, TestGridObject

# -------------------------
# ✅ GridLocation
# -------------------------


def test_grid_location_construction():
    loc_default = GridLocation()
    loc_2d = GridLocation(5, 6)
    loc_3d = GridLocation(7, 8, 1)

    assert (loc_default.row(), loc_default.col(), loc_default.layer()) == (0, 0, 0)
    assert (loc_2d.row(), loc_2d.col(), loc_2d.layer()) == (5, 6, 0)
    assert (loc_3d.row(), loc_3d.col(), loc_3d.layer()) == (7, 8, 1)


def test_grid_location_properties():
    loc = GridLocation()
    loc.set_row(10)
    loc.set_col(20)
    loc.set_layer(2)

    assert loc.row() == 10
    assert loc.col() == 20
    assert loc.layer() == 2


# -------------------------
# ✅ Orientation
# -------------------------


def test_orientation_enum():
    assert Orientation.UP == 0
    assert Orientation.DOWN == 1
    assert Orientation.LEFT == 2
    assert Orientation.RIGHT == 3


# -------------------------
# ✅ GridObject / TestGridObject
# -------------------------


def test_testgridobject_init_flexibility():
    obj = TestGridObject()

    obj.init(1, GridLocation(1, 2, 0))
    assert obj.type_id() == 1
    loc = obj.location()
    assert (loc.row(), loc.col(), loc.layer()) == (1, 2, 0)

    obj.init(2, 3, 4)
    assert obj.type_id() == 2
    loc = obj.location()
    assert (loc.row(), loc.col(), loc.layer()) == (3, 4, 0)

    obj.init(3, 6, 7, 1)
    assert obj.type_id() == 3
    loc = obj.location()
    assert (loc.row(), loc.col(), loc.layer()) == (6, 7, 1)


def test_grid_object_id_access():
    obj = TestGridObject()
    obj.init(5, 0, 0)
    obj.set_id(123)
    assert obj.id() == 123


def test_grid_object_location_access():
    obj = TestGridObject()
    obj.init(10, 1, 2)

    loc = obj.location()
    assert (loc.row(), loc.col(), loc.layer()) == (1, 2, 0)

    new_loc = GridLocation(9, 8, 3)
    obj.set_location(new_loc)
    loc = obj.location()
    assert (loc.row(), loc.col(), loc.layer()) == (9, 8, 3)


def test_grid_object_obs_behavior():
    obj = TestGridObject()
    obj.init(99, 4, 6)

    obs_array = np.zeros(5, dtype=np.uint8)
    offsets = [0, 1, 2, 3, 4]
    obj.obs(obs_array, offsets)  # No assignment to result
    for i, expected in enumerate([4 + 6 + i for i in range(5)]):
        assert obs_array[i] == expected


def test_grid_location_repr():
    loc = GridLocation(2, 3, 1)
    assert repr(loc) == "GridLocation(row=2, col=3, layer=1)"
