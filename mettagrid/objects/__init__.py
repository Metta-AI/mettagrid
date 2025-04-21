"""Objects module for MettaGrid."""

# Import all object types for easier access
from mettagrid.objects.constants import InventoryItem, ObjectType, GridLayer, Events
from mettagrid.objects.agent import Agent
from mettagrid.objects.altar import Altar
from mettagrid.objects.armory import Armory
from mettagrid.objects.converter import Converter
from mettagrid.objects.factory import Factory
from mettagrid.objects.generator import Generator
from mettagrid.objects.lab import Lab
from mettagrid.objects.lasery import Lasery
from mettagrid.objects.metta_object import MettaObject
from mettagrid.objects.mine import Mine
from mettagrid.objects.production_handler import ProductionHandler, CoolDownHandler
from mettagrid.objects.temple import Temple
from mettagrid.objects.wall import Wall

# Create __all__ to define what gets imported with `from mettagrid.objects import *`
__all__ = [
    # Constants
    'InventoryItem', 'ObjectType', 'GridLayer', 'Events',
    
    # Object types
    'Agent', 'Altar', 'Armory', 'Converter', 'Factory', 'Generator',
    'Lab', 'Lasery', 'MettaObject', 'Mine', 'Temple', 'Wall',
    
    # Handlers
    'ProductionHandler', 'CoolDownHandler'
]