"""Actions module for MettaGrid."""

# Import all action types for easier access
from mettagrid.actions.actions import MettaActionHandler
from mettagrid.actions.attack import Attack
from mettagrid.actions.attack_nearest import AttackNearest
from mettagrid.actions.change_color import ChangeColorAction
from mettagrid.actions.get_output import GetOutput
from mettagrid.actions.move import Move
from mettagrid.actions.noop import Noop
from mettagrid.actions.put_recipe_items import PutRecipeItems
from mettagrid.actions.rotate import Rotate
from mettagrid.actions.swap import Swap

# Create __all__ to define what gets imported with `from mettagrid.actions import *`
__all__ = [
    # Base class
    'MettaActionHandler',
    
    # Action types
    'Attack', 'AttackNearest', 'ChangeColorAction', 'GetOutput',
    'Move', 'Noop', 'PutRecipeItems', 'Rotate', 'Swap'
]