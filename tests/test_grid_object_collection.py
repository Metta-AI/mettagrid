"""
Extended unit tests for the grid_object module covering collections of objects.

Tests interactions between multiple grid objects and more complex behaviors.
"""

import numpy as np
import pytest

from mettagrid.grid_object import ConcreteGridObject, GridLocation, PyGridObject


class TestGridObjectCollection:
    """Test collection of grid objects and interactions."""

    @pytest.fixture
    def grid_objects(self):
        """Fixture to create a collection of test objects."""
        objects = []
        for i in range(5):
            obj = ConcreteGridObject()
            obj.py_init(i % 3, i * 2, i * 3, i % 2)
            obj.py_set_id(i + 100)
            objects.append(obj)
        return objects

    def test_object_uniqueness(self, grid_objects):
        """Test that objects maintain unique IDs."""
        ids = [obj.py_id() for obj in grid_objects]
        assert len(ids) == len(set(ids))  # All IDs should be unique

    def test_type_filtering(self, grid_objects):
        """Test filtering objects by type."""
        # Get objects of type 0
        type_0_objects = [obj for obj in grid_objects if obj.py_type_id() == 0]
        assert len(type_0_objects) == 2  # Should be 2 objects of type 0

        # Verify their indices in the original collection
        indices = [grid_objects.index(obj) for obj in type_0_objects]
        assert sorted(indices) == [0, 3]  # Objects at index 0 and 3 should be type 0

    def test_layer_filtering(self, grid_objects):
        """Test filtering objects by layer."""
        # Get objects on layer 0
        layer_0_objects = [obj for obj in grid_objects if obj.py_location().py_layer() == 0]
        assert len(layer_0_objects) == 3  # Should be 3 objects on layer 0

        # Verify their indices
        indices = [grid_objects.index(obj) for obj in layer_0_objects]
        assert sorted(indices) == [0, 2, 4]  # Objects at indices 0, 2, 4 should be on layer 0

    def test_object_relocation(self, grid_objects):
        """Test changing object locations."""
        # Change locations
        for i, obj in enumerate(grid_objects):
            new_loc = GridLocation(i * 3, i * 4, i % 2)
            obj.py_set_location(new_loc)

        # Verify new locations
        for i, obj in enumerate(grid_objects):
            loc = obj.py_location()
            assert loc.py_row() == i * 3
            assert loc.py_col() == i * 4
            assert loc.py_layer() == i % 2

    def test_observations_across_objects(self, grid_objects):
        """Test retrieving observations from multiple objects."""
        # Set up observation arrays
        obs_arrays = [np.zeros(2, dtype=np.uint8) for _ in range(len(grid_objects))]
        offsets = [0, 1]

        # Get observations from each object
        for i, obj in enumerate(grid_objects):
            obj.py_obs(obs_arrays[i], offsets)

        # Verify results based on implementation of TestObject.obs
        for i, obj in enumerate(grid_objects):
            loc = obj.py_location()
            assert obs_arrays[i][0] == loc.py_row() + loc.py_col() + 0
            assert obs_arrays[i][1] == loc.py_row() + loc.py_col() + 1


class TestPyGridObjectCollection:
    """Test collection of pure Python grid objects."""

    @pytest.fixture
    def py_grid_objects(self):
        """Fixture to create a collection of pure Python grid objects."""
        objects = []
        for i in range(5):
            obj = PyGridObject(i + 100, i % 3, i * 2, i * 3, i % 2)
            objects.append(obj)
        return objects

    def test_object_uniqueness(self, py_grid_objects):
        """Test that objects maintain unique IDs."""
        ids = [obj.id for obj in py_grid_objects]
        assert len(ids) == len(set(ids))  # All IDs should be unique

    def test_type_filtering(self, py_grid_objects):
        """Test filtering objects by type."""
        # Get objects of type 0
        type_0_objects = [obj for obj in py_grid_objects if obj.type_id == 0]
        assert len(type_0_objects) == 2  # Should be 2 objects of type 0
