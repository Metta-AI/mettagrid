import pytest

from mettagrid.action_handler import ActionHandler
from mettagrid.grid import Grid
from mettagrid.grid_object import PyGridLocation, PyGridObject, TestGridObject


class TestActionHandler(ActionHandler):
    """Concrete implementation of ActionHandler for testing"""

    def __init__(self, config=None, action_name="test_action"):
        # No need to call super().__init__ - Cython handles this differently
        # The C++ objects are initialized in __cinit__
        self._max_arg = 3  # Example value for testing

    def max_arg(self):
        # Override the parent method
        return self._max_arg

    # Override the internal C++ method in Python for testing
    def handle_action(self, actor_id, actor_object_id, arg, timestep):
        # Simple implementation that just returns success based on arg value
        return arg <= self._max_arg


@pytest.fixture
def test_grid():
    """Create a test grid with proper layer configuration"""
    return Grid(10, 10, [0, 0, 0])  # Ensure we have at least 3 layers for different object types


@pytest.fixture
def test_object():
    """Create a test object to use as an actor"""
    obj = TestGridObject()
    obj.init(1, PyGridLocation(1, 1))  # Type 1, position (1,1)
    return obj


@pytest.fixture
def py_test_object():
    """Create a PyGridObject to use as an actor"""
    return PyGridObject(obj_id=1, type_id=1, row=1, col=1, layer=0)


@pytest.fixture
def setup_grid_with_object(test_grid: Grid, test_object):
    """Setup fixture that adds the object to the grid using Python-accessible methods"""
    test_grid.py_add_object(test_object)
    return test_grid, test_object


@pytest.fixture
def setup_grid_with_py_object(test_grid: Grid, py_test_object):
    """Setup fixture that adds the PyGridObject to the grid"""
    # Since PyGridObject doesn't have a C++ pointer, we'll mock this behavior for testing
    import os

    os.environ["PYTEST_CURRENT_TEST"] = "True"
    test_grid.py_add_object(py_test_object)

    # For testing purposes, we might need to add a method to directly add
    # a PyGridObject to the grid without C++ pointers
    return test_grid, py_test_object


def test_action_handler_basics():
    """Test basic properties of the action handler"""
    handler = TestActionHandler({"priority": 1}, "test_action")
    assert handler.action_name() == "test_action"
    assert handler.max_arg() == 3


def test_handle_action_with_testgridobject(setup_grid_with_object):
    """Test that the action handler processes actions correctly with TestGridObject"""
    test_grid, test_object = setup_grid_with_object
    handler = TestActionHandler()
    # Don't forget to initialize the handler with the grid
    handler.init(test_grid)

    # Valid action (arg <= max_arg)
    result = handler.handle_action(1, test_object.id(), 2, 100)
    assert result is True

    # Invalid action (arg > max_arg)
    result = handler.handle_action(1, test_object.id(), 5, 100)
    assert result is False


def test_handle_action_with_pygridobject(setup_grid_with_py_object):
    """Test that the action handler processes actions correctly with PyGridObject"""
    test_grid, py_object = setup_grid_with_py_object
    handler = TestActionHandler()
    # Initialize the handler with the grid
    handler.init(test_grid)

    # Valid action (arg <= max_arg)
    result = handler.handle_action(1, py_object.id(), 2, 100)
    assert result is True

    # Invalid action (arg > max_arg)
    result = handler.handle_action(1, py_object.id(), 5, 100)
    assert result is False


def test_action_handler_with_py_grid_objects():
    """Test action handler with pure Python objects without grid"""
    handler = TestActionHandler()

    # We can test the handler's logic directly without needing grid integration
    py_object = PyGridObject(obj_id=42)

    # Valid action
    result = handler.handle_action(1, py_object.id(), 3, 100)
    assert result is True

    # Invalid action
    result = handler.handle_action(1, py_object.id(), 4, 100)
    assert result is False
