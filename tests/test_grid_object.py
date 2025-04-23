"""
Unit tests for the grid_object Cython module.

Tests both the C++ wrapped functionality and the pure Python versions.
"""

import numpy as np
import pytest

from mettagrid.grid_object import ConcreteGridObject, GridLocation, PyGridLocation, PyGridObject, PyOrientation


class TestGridLocation:
    """Test the GridLocation class that wraps CppGridLocation."""

    def test_default_constructor(self):
        """Test that default constructor initializes to (0,0,0)"""
        loc = GridLocation()
        assert loc.py_row() == 0
        assert loc.py_col() == 0
        assert loc.py_layer() == 0

    def test_constructor_with_args(self):
        """Test constructor with row, col, layer arguments"""
        loc = GridLocation(10, 20, 5)
        assert loc.py_row() == 10
        assert loc.py_col() == 20
        assert loc.py_layer() == 5

    def test_setters_getters(self):
        """Test setters and getters for row, col, layer"""
        loc = GridLocation()

        # Test setters
        loc.py_set_row(15)
        loc.py_set_col(25)
        loc.py_set_layer(3)

        # Verify values
        assert loc.py_row() == 15
        assert loc.py_col() == 25
        assert loc.py_layer() == 3

    def test_equality(self):
        """Test equality comparison operator"""
        loc1 = GridLocation(1, 2, 3)
        loc2 = GridLocation(1, 2, 3)
        loc3 = GridLocation(4, 5, 6)

        assert loc1 == loc2
        assert loc1 != loc3
        assert loc2 != loc3

    def test_repr(self):
        """Test string representation"""
        loc = GridLocation(7, 8, 9)
        assert repr(loc) == "GridLocation(row=7, col=8, layer=9)"


class TestPyGridLocation:
    """Test the pure Python GridLocation class."""

    def test_default_constructor(self):
        """Test that default constructor initializes to (0,0,0)"""
        loc = PyGridLocation()
        assert loc.py_row() == 0
        assert loc.py_col() == 0
        assert loc.py_layer() == 0

    def test_constructor_with_args(self):
        """Test constructor with row, col, layer arguments"""
        loc = PyGridLocation(10, 20, 5)
        assert loc.py_row() == 10
        assert loc.py_col() == 20
        assert loc.py_layer() == 5

    def test_equality(self):
        """Test equality comparison operator"""
        loc1 = PyGridLocation(1, 2, 3)
        loc2 = PyGridLocation(1, 2, 3)
        loc3 = PyGridLocation(4, 5, 6)

        assert loc1 == loc2
        assert loc1 != loc3
        assert loc2 != loc3

    def test_repr(self):
        """Test string representation"""
        loc = PyGridLocation(7, 8, 9)
        assert repr(loc) == "PyGridLocation(row=7, col=8, layer=9)"


class TestPyOrientation:
    """Test the PyOrientation enum wrapper."""

    def test_orientation_values(self):
        """Test that orientation values match the C++ enum"""
        assert PyOrientation.UP == 0
        assert PyOrientation.DOWN == 1
        assert PyOrientation.LEFT == 2
        assert PyOrientation.RIGHT == 3


class TestGridObjectClass:
    """
    Test the GridObject functionality using ConcreteGridObject implementation.
    """

    @pytest.fixture
    def grid_object(self):
        """Fixture that returns a ConcreteGridObject instance."""
        return ConcreteGridObject()

    def test_init_with_location(self, grid_object):
        """Test initialization with a GridLocation"""
        try:
            loc = GridLocation(5, 10, 2)
            # Print some debug info
            print(f"Created location: {loc}")

            # Verify the grid_object is valid
            if not hasattr(grid_object, "py_init"):
                pytest.skip("Grid object doesn't have py_init method")

            grid_object.py_init(1, loc)

            # Verify values
            type_id = grid_object.py_type_id()
            print(f"Type ID: {type_id}")
            assert type_id == 1

            result_loc = grid_object.py_location()
            print(f"Result location: {result_loc}")
            assert result_loc.py_row() == 5
            assert result_loc.py_col() == 10
            assert result_loc.py_layer() == 2
        except Exception as e:
            print(f"Error during test: {e}")
            raise

    def test_init_with_row_col(self, grid_object):
        """Test initialization with row and col (default layer)"""
        grid_object.py_init(2, 15, 25)

        # Verify values
        assert grid_object.py_type_id() == 2
        result_loc = grid_object.py_location()
        assert result_loc.py_row() == 15
        assert result_loc.py_col() == 25
        assert result_loc.py_layer() == 0  # Default layer

    def test_init_with_row_col_layer(self, grid_object):
        """Test initialization with row, col, and layer"""
        grid_object.py_init(3, 20, 30, 4)

        # Verify values
        assert grid_object.py_type_id() == 3
        result_loc = grid_object.py_location()
        assert result_loc.py_row() == 20
        assert result_loc.py_col() == 30
        assert result_loc.py_layer() == 4

    def test_init_invalid_args(self, grid_object):
        """Test that invalid init arguments raise ValueError"""
        with pytest.raises(ValueError):
            grid_object.py_init(1, "invalid")

        with pytest.raises(ValueError):
            grid_object.py_init(1, 10, None)

    def test_set_get_id(self, grid_object):
        """Test setting and getting the object ID"""
        grid_object.py_set_id(12345)
        assert grid_object.py_id() == 12345

    def test_set_get_location(self, grid_object):
        """Test setting and getting location"""
        loc = GridLocation(7, 8, 9)
        grid_object.py_set_location(loc)

        result_loc = grid_object.py_location()
        assert result_loc.py_row() == 7
        assert result_loc.py_col() == 8
        assert result_loc.py_layer() == 9

    def test_obs_method(self, grid_object):
        """Test the observation method"""
        # Set location first
        loc = GridLocation(3, 4, 0)
        grid_object.py_set_location(loc)

        # Create observation array and offsets
        obs_array = np.zeros(3, dtype=np.uint8)
        offsets = [0, 1, 2]

        # Call obs method
        grid_object.py_obs(obs_array, offsets)

        # Verify results based on CppConcreteGridObject implementation
        # According to the implementation, obs[i] = row + col + i
        assert obs_array[0] == 3 + 4 + 0
        assert obs_array[1] == 3 + 4 + 1
        assert obs_array[2] == 3 + 4 + 2


class TestPyGridObject:
    """Test the pure Python GridObject class."""

    def test_constructor(self):
        """Test constructor with arguments"""
        obj = PyGridObject(1, 2, 3, 4, 5)
        assert obj.id == 1
        assert obj.type_id == 2
        assert obj.location.row == 3
        assert obj.location.col == 4
        assert obj.location.layer == 5

    def test_repr(self):
        """Test string representation"""
        obj = PyGridObject(1, 2, 3, 4, 5)
        assert "PyGridObject" in repr(obj)
        assert "id=1" in repr(obj)
        assert "type_id=2" in repr(obj)
        assert "location=" in repr(obj)
