"""
Unit tests for the GridObject framework.

This module contains pytest-based unit tests that verify the functionality
of the GridObject system, including GridLocation, Orientation, and the
TestGridObject implementation.
"""

import numpy as np

from mettagrid.grid_object import GridLocation, Orientation, TestGridObject


def test_grid_location_init():
    """Test the different constructors for GridLocation."""
    # Test default constructor (0,0,0)
    default_loc = GridLocation()
    assert default_loc.row == 0
    assert default_loc.col == 0
    assert default_loc.layer == 0

    # Test two-argument constructor (row, col, layer=0)
    two_arg_loc = GridLocation(10, 20)
    assert two_arg_loc.row == 10
    assert two_arg_loc.col == 20
    assert two_arg_loc.layer == 0

    # Test three-argument constructor (row, col, layer)
    three_arg_loc = GridLocation(30, 40, 2)
    assert three_arg_loc.row == 30
    assert three_arg_loc.col == 40
    assert three_arg_loc.layer == 2


def test_grid_location_properties():
    """Test the property getters and setters for GridLocation."""
    test_loc = GridLocation(5, 7, 3)

    # Test getters for both primary properties and aliases
    assert test_loc.row == 5
    assert test_loc.col == 7
    assert test_loc.layer == 3

    # Test setters for properties
    test_loc.row = 10
    test_loc.col = 20
    test_loc.layer = 1

    assert test_loc.row == 10
    assert test_loc.col == 20
    assert test_loc.layer == 1


def test_orientation_enum():
    """Test the Orientation enum constants."""
    assert Orientation.UP == 0
    assert Orientation.DOWN == 1
    assert Orientation.LEFT == 2
    assert Orientation.RIGHT == 3


def test_grid_object_init():
    """Test the different initialization methods for GridObject."""
    test_obj = TestGridObject()

    # Test initialization with GridLocation
    test_loc = GridLocation(5, 10, 2)
    test_obj.init(42, test_loc)
    assert test_obj.type_id == 42
    assert test_obj.location.row == 5
    assert test_obj.location.col == 10
    assert test_obj.location.layer == 2

    # Test initialization with row, col (layer defaults to 0)
    test_obj.init(43, 15, 25)
    assert test_obj.type_id == 43
    assert test_obj.location.row == 15
    assert test_obj.location.col == 25
    assert test_obj.location.layer == 0

    # Test initialization with row, col, layer
    test_obj.init(44, 30, 40, 3)
    assert test_obj.type_id == 44
    assert test_obj.location.row == 30
    assert test_obj.location.col == 40
    assert test_obj.location.layer == 3


def test_grid_object_id():
    """Test the ID property of GridObject."""
    test_obj = TestGridObject()
    test_obj.init(42, 5, 10)

    # Test ID setter and getter
    test_obj.id = 12345
    assert test_obj.id == 12345


def test_grid_object_location():
    """Test the location property of GridObject."""
    test_obj = TestGridObject()
    test_obj.init(42, 5, 10)

    # Test location property getter
    obj_location = test_obj.location
    assert obj_location.row == 5
    assert obj_location.col == 10
    assert obj_location.layer == 0

    # Test location property setter
    new_location = GridLocation(15, 25, 3)
    test_obj.location = new_location

    updated_location = test_obj.location
    assert updated_location.row == 15
    assert updated_location.col == 25
    assert updated_location.layer == 3


def test_grid_object_obs():
    """Test the observation generation functionality."""
    test_obj = TestGridObject()
    test_obj.init(42, 5, 7)

    # Create observation array and offset list
    observation_array = np.zeros(5, dtype=np.uint8)
    offset_indices = [0, 1, 2, 3, 4]

    # Generate observations
    result = test_obj.obs(observation_array, offset_indices)

    # In our test implementation, each element should be row + col + offset_index
    # (5 + 7 + index)
    for i, _offset in enumerate(offset_indices):
        expected_value = 5 + 7 + i
        assert result[i] == expected_value, f"Observation at index {i} incorrect"


if __name__ == "__main__":
    """Run all tests manually if module is executed directly."""
    test_grid_location_init()
    test_grid_location_properties()
    test_orientation_enum()
    test_grid_object_init()
    test_grid_object_id()
    test_grid_object_location()
    test_grid_object_obs()
    print("All tests passed!")
