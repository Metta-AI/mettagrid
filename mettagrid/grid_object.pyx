#distutils : language = c++
#cython : language_level = 3
#cython : boundscheck = False
#cython : wraparound = False
#cython : initializedcheck = False
#cython : cdivision = True
"""
Python wrapper implementation for the grid object system.

This module provides Pythonic interfaces to the C++ grid object system,
allowing for easy manipulation of grid-based objects from Python code.
"""

from libc.stdlib cimport malloc, free
from libc.string cimport memcpy
import numpy as np
cimport numpy as np
from libcpp.vector cimport vector

#Import the C++ definitions
from mettagrid.cpp_grid_object cimport *

class Orientation:
    """
    Cardinal directions for object orientation.
    
    This class provides named constants for the orientation enum,
    making it more Pythonic to work with directions.
    """
    UP = Up
    DOWN = Down
    LEFT = Left
    RIGHT = Right

cdef class GridLocation:
    """
    Represents a location in a multi-layered grid.
    
    Attributes:
        row (int): Row coordinate in the grid
        col (int): Column coordinate in the grid
        layer (int): Layer identifier (defaults to 0)
    """
    
    def __cinit__(self, unsigned int row=0, unsigned int col=0, unsigned short layer=0):
        """
        Initialize a new grid location with the given coordinates.
        
        Args:
            row (int): Row coordinate
            col (int): Column coordinate
            layer (int): Layer identifier
        """
        self._cpp_loc = CppGridLocation(row, col, layer)

    @property
    def row(self):
        """Row coordinate in the grid."""
        return self._cpp_loc.row

    @row.setter
    def row(self, unsigned int value):
        """Set the row coordinate."""
        self._cpp_loc.row = value

    @property
    def col(self):
        """Column coordinate in the grid."""
        return self._cpp_loc.col
    
    @col.setter
    def col(self, unsigned int value):
        """Set the column coordinate."""
        self._cpp_loc.col = value

    @property
    def layer(self):
        """Layer identifier for multi-layered grids."""
        return self._cpp_loc.layer
    
    @layer.setter
    def layer(self, unsigned short value):
        """Set the layer identifier."""
        self._cpp_loc.layer = value
    
    def __repr__(self):
        """String representation of the grid location."""
        return f"GridLocation(row={self.row}, col={self.col}, layer={self.layer})"

cdef class GridObject:
    """
    Abstract base class for objects that exist on a grid.
    
    This class wraps the C++ CppGridObject class and provides a Pythonic interface
    for initializing and manipulating grid objects.
    
    Attributes:
        id (int): Unique object identifier
        type_id (int): Type identifier for this object (read-only)
        location (GridLocation): Current grid location
    """
    
    def __cinit__(self):
        """Initialize the C++ pointer as NULL and ownership as False."""
        self._cpp_obj = NULL
        self._owns_ptr = False
    
    def __dealloc__(self):
        """Clean up the C++ object if we own it."""
        if self._cpp_obj is not NULL and self._owns_ptr:
            del self._cpp_obj

    def init(self, unsigned short type_id, object location_or_row, col=None, layer=None):
        """
        Initialize the grid object with a type and location.
        
        This method supports multiple calling conventions:
        1. init(type_id, GridLocation)
        2. init(type_id, row, col)
        3. init(type_id, row, col, layer)
        
        Args:
            type_id (int): Type identifier for this object
            location_or_row: Either a GridLocation or a row coordinate
            col (int, optional): Column coordinate (if location_or_row is a row)
            layer (int, optional): Layer identifier (if not using GridLocation)
            
        Raises:
            ValueError: If the arguments don't match any of the supported patterns
        """
        if isinstance(location_or_row, GridLocation):
        #Case 1 : init(type_id, GridLocation)
            location = location_or_row
            self._cpp_obj.cpp_init(type_id, (<GridLocation>location)._cpp_loc)
        elif col is not None and layer is None:
        #Case 2 : init(type_id, row, col)
            row = location_or_row
            self._cpp_obj.cpp_init(type_id, row, col)
        elif col is not None and layer is not None:
        #Case 3 : init(type_id, row, col, layer)
            row = location_or_row
            self._cpp_obj.cpp_init(type_id, row, col, layer)
        else:
            raise ValueError("Invalid arguments to init(). Expected either: "
                             "(type_id, GridLocation), (type_id, row, col), or "
                             "(type_id, row, col, layer)")
    
    @property
    def id(self):
        """Unique object identifier."""
        return self._cpp_obj.id
    
    @id.setter
    def id(self, unsigned int value):
        """Set the unique object identifier."""
        self._cpp_obj.id = value
    
    @property
    def type_id(self):
        """Type identifier for this object (read-only)."""
        return self._cpp_obj.objectTypeId
    
    @property
    def location(self):
        """Current grid location."""
        cdef GridLocation loc = GridLocation.__new__(GridLocation)
        loc._cpp_loc = self._cpp_obj.location
        return loc
    
    @location.setter
    def location(self, GridLocation loc):
        """Set the current grid location."""
        self._cpp_obj.location = loc._cpp_loc
    
    def obs(self, np.ndarray[unsigned char, ndim=1] obs_array, list offsets):
        """
        Generate observations about this object.
        
        This method must be implemented by subclasses.
        
        Args:
            obs_array: NumPy array to store observations
            offsets: List of observation indices/offsets
            
        Raises:
            NotImplementedError: If called on the base class
        """
        raise NotImplementedError("Subclasses must implement obs() method")

cdef class TestGridObject(GridObject):
    """
    Concrete implementation of GridObject for testing purposes.
    
    This class provides a simple implementation that generates observations
    based on the object's location, for use in testing.
    """
    
    def __cinit__(self):
        """
        Initialize with a new CppTestGridObject.
        
        Creates the C++ implementation object and takes ownership of it.
        """
        self._cpp_obj = new CppTestGridObject()
        self._owns_ptr = True
    
    def obs(self, np.ndarray[unsigned char, ndim=1] obs_array, list offsets):
        """
        Implementation of the observation method for testing.
        
        Generates observations based on a simple formula: row + col + offset_index
        
        Args:
            obs_array: NumPy array to store observations
            offsets: List of observation indices/offsets
            
        Returns:
            The filled observation array
        """
        
        #Convert Python list to C++ vector
        cdef vector[unsigned int] cpp_offsets
        for offset in offsets:
            cpp_offsets.push_back(<unsigned int>offset)

        # Call the C++ implementation
        cdef cpp_ObsType* obs_ptr = &obs_array[0]
        # Call the C++ implementation with the dummy parameter to avoid ambiguity
        (<CppTestGridObject*>self._cpp_obj).cpp_obs(&obs_array[0], cpp_offsets, 0)

        return obs_array