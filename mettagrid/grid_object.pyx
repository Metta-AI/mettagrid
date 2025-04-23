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

from mettagrid.cpp_grid_object cimport *

# -------- GridLocation --------
cdef class GridLocation:
    """
    Represents a location in a multi-layered grid.
    """
    def __cinit__(self, unsigned int row=0, unsigned int col=0, unsigned short layer=0):
        self._cpp_loc = CppGridLocation(row, col, layer)

    # C++ core methods - using cdef for efficiency
    cdef unsigned int row(self):
        return self._cpp_loc.row

    cdef void set_row(self, unsigned int value):
        self._cpp_loc.row = value

    cdef unsigned int col(self):
        return self._cpp_loc.col

    cdef void set_col(self, unsigned int value):
        self._cpp_loc.col = value

    cdef unsigned short layer(self):
        return self._cpp_loc.layer

    cdef void set_layer(self, unsigned short value):
        self._cpp_loc.layer = value
        
    # Python-accessible wrapper methods
    def py_row(self):
        return self.row()
        
    def py_set_row(self, value):
        self.set_row(value)
        
    def py_col(self):
        return self.col()
        
    def py_set_col(self, value):
        self.set_col(value)
        
    def py_layer(self):
        return self.layer()
        
    def py_set_layer(self, value):
        self.set_layer(value)

    def __richcmp__(self, GridLocation other, int op):
        if op == 2:  # ==
            return (self._cpp_loc.row == other._cpp_loc.row and
                    self._cpp_loc.col == other._cpp_loc.col and
                    self._cpp_loc.layer == other._cpp_loc.layer)
        elif op == 3:  # !=
            return not (self._cpp_loc.row == other._cpp_loc.row and
                      self._cpp_loc.col == other._cpp_loc.col and
                      self._cpp_loc.layer == other._cpp_loc.layer)
        else:
            return NotImplemented

    def __repr__(self):
        return f"GridLocation(row={self._cpp_loc.row}, col={self._cpp_loc.col}, layer={self._cpp_loc.layer})"

# -------- GridObject Base --------
cdef class GridObject:
    """
    Abstract base class for grid-resident objects.
    Wraps the C++ CppGridObject class.
    """

    def __cinit__(self):
        self._cpp_obj = NULL
        self._owns_ptr = False

    def __dealloc__(self):
        if self._cpp_obj is not NULL and self._owns_ptr:
            del self._cpp_obj

    cpdef void init(self, unsigned short type_id, object location_or_row, object col=None, object layer=None):
        if isinstance(location_or_row, GridLocation):
            location = location_or_row
            self._cpp_obj.cpp_init(type_id, (<GridLocation>location)._cpp_loc)
        elif col is not None and layer is None:
            row = location_or_row
            self._cpp_obj.cpp_init(type_id, row, col)
        elif col is not None and layer is not None:
            row = location_or_row
            self._cpp_obj.cpp_init(type_id, row, col, layer)
        else:
            raise ValueError("Invalid arguments to init(). Expected either: "
                             "(type_id, GridLocation), (type_id, row, col), or "
                             "(type_id, row, col, layer)")

     # C++ core methods - using cpdef for efficiency but still Python-accessible
    cpdef unsigned int id(self):
        return self._cpp_obj.id

    cpdef void set_id(self, unsigned int value):
        self._cpp_obj.id = value

    cpdef cpp_TypeId type_id(self):
        return self._cpp_obj.objectTypeId

    cpdef GridLocation location(self):
        cdef GridLocation loc = GridLocation.__new__(GridLocation)
        loc._cpp_loc = self._cpp_obj.location
        return loc

    cpdef void set_location(self, GridLocation loc):
        self._cpp_obj.location = loc._cpp_loc

    cpdef void obs(self, np.ndarray[unsigned char, ndim=1] obs_array, list offsets):
        raise NotImplementedError("Subclasses must implement obs() method")
        
    # Python-accessible wrapper methods
    def py_id(self):
        return self.id()
        
    def py_set_id(self, value):
        self.set_id(value)
        
    def py_type_id(self):
        return self.type_id()
        
    def py_location(self):
        return self.location()
        
    def py_set_location(self, loc):
        self.set_location(loc)
        
    def py_init(self, type_id, location_or_row, col=None, layer=None):
        self.init(type_id, location_or_row, col, layer)
        
    def py_obs(self, obs_array, offsets):
        self.obs(obs_array, offsets)


cdef class ConcreteGridObject(GridObject):
    """
    Concrete implementation of GridObject for testing.
    Wraps the C++ CppConcreteGridObject class.
    """
    
    def __cinit__(self):
        # Make sure we're actually creating a valid C++ object
        self._cpp_obj = new CppConcreteGridObject()
        self._owns_ptr = True
    
    cpdef void obs(self, np.ndarray[unsigned char, ndim=1] obs_array, list offsets):
        if self._cpp_obj is NULL:
            raise ValueError("C++ object is NULL")
            
        cdef vector[unsigned int] cpp_offsets
        for offset in offsets:
            cpp_offsets.push_back(offset)
        
        # use the dummy version to disambiguate
        (<CppConcreteGridObject*>self._cpp_obj).cpp_obs(
            <cpp_ObsType*>obs_array.data, 
            cpp_offsets,
            0 # ignored dummy parameter
        )

# Python-accessible data classes

class PyOrientation:
    """
    Cardinal directions for object orientation.
    """
    UP = Up
    DOWN = Down
    LEFT = Left
    RIGHT = Right


class PyGridLocation:
    """Python data class version of GridLocation for testing"""
    def __init__(self, row=0, col=0, layer=0):
        self.row = row
        self.col = col
        self.layer = layer
        
    def __eq__(self, other):
        if not isinstance(other, PyGridLocation):
            return False
        return (self.row == other.row and 
                self.col == other.col and 
                self.layer == other.layer)
                
    def __repr__(self):
        return f"PyGridLocation(row={self.row}, col={self.col}, layer={self.layer})"

    def py_row(self):
        return self.row
        
    def py_col(self):
        return self.col
        
    def py_layer(self):
        return self.layer

class PyGridObject:
    """Python data class version of GridObject for testing"""
    def __init__(self, obj_id=0, type_id=0, row=0, col=0, layer=0):
        self.id = obj_id
        self.type_id = type_id
        self.location = PyGridLocation(row, col, layer)
        
    def __repr__(self):
        return f"PyGridObject(id={self.id}, type_id={self.type_id}, location={self.location})"

    def id(self):
        return self.obj_id
        
    def location(self):
        return PyGridLocation(self.row, self.col, self.layer)
        
    def py_id(self):
        return self.obj_id
        
    def py_type_id(self):
        return self.type_id
        
    def py_location(self):
        return self.location()