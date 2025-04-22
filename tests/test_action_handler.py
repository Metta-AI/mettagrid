import pytest

from mettagrid.action_handler import ActionHandler
from mettagrid.grid import Grid
from mettagrid.grid_object import GridLocation, TestGridObject


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
    obj.init(1, GridLocation(1, 1))  # Type 1, position (1,1)
    return obj


@pytest.fixture
def setup_grid_with_object(test_grid: Grid, test_object):
    """Setup fixture that adds the object to the grid using Python-accessible methods"""
    # Create a Python-accessible wrapper method that can access the Cython method
    # You'll need to add this method to your Grid class
    test_grid.py_add_object(test_object)
    return test_grid, test_object


def test_action_handler_basics():
    """Test basic properties of the action handler"""
    handler = TestActionHandler({"priority": 1}, "test_action")
    assert handler.action_name() == "test_action"
    assert handler.max_arg() == 3


def test_handle_action(setup_grid_with_object):
    """Test that the action handler processes actions correctly"""
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
