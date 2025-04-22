#distutils : language = c++
"""
Cython definitions for Python wrapper classes of the grid object system.
This file declares the Python-accessible classes that wrap the C++ implementation.
"""
from libcpp.vector cimport vector
import numpy as np
cimport numpy as np

#Import from our cpp_grid_object.pxd file(note the syntax)
from mettagrid.cpp_grid_object cimport CppGridLocation, CppGridObject, CppTestGridObject
from mettagrid.cpp_grid_object cimport cpp_TypeId, cpp_GridObjectId, cpp_GridCoord, cpp_Layer, cpp_ObsType, cpp_Orientation

#Python wrapper for C++ GridLocation
cdef class GridLocation:
    #The wrapped C++ object
    cdef CppGridLocation _cpp_loc

#Abstract base class for grid objects in Python
cdef class GridObject:
    #The wrapped C++ object and ownership flag
    cdef CppGridObject* _cpp_obj
    cdef bint _owns_ptr  # True if this Python object owns the C++ pointer

#Concrete implementation for testing
cdef class TestGridObject(GridObject):
    #Inherits members from GridObject
    pass