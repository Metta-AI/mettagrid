"""
Cython definitions for C++ grid object classes.
This file provides the interface between C++ and Python.
"""
from libcpp.vector cimport vector

cdef extern from "cpp_grid_object.hpp":

    #Type definitions matching the C++ header
    ctypedef unsigned short cpp_Layer      # Layer identifier type
    ctypedef unsigned short cpp_TypeId     # Object type identifier 
    ctypedef unsigned int cpp_GridCoord    # Grid coordinate type
    ctypedef unsigned char cpp_ObsType     # Observation data type
    ctypedef unsigned int cpp_GridObjectId # Unique object identifier

    #Grid location class definition
    cdef cppclass CppGridLocation:
        cpp_GridCoord row
        cpp_GridCoord col
        cpp_Layer layer

        #Constructors
        CppGridLocation()
        CppGridLocation(cpp_GridCoord row, cpp_GridCoord col, cpp_Layer layer)
        CppGridLocation(cpp_GridCoord row, cpp_GridCoord col)

    #Orientation enum definition
    ctypedef enum cpp_Orientation:
        Up = 0    # Facing upward
        Down = 1  # Facing downward
        Left = 2  # Facing left
        Right = 3 # Facing right

    #Abstract base class for grid objects
    cdef cppclass CppGridObject:
        #Public members
        cpp_GridObjectId id
        CppGridLocation location
        cpp_TypeId objectTypeId

        #Constructor and initialization methods
        CppGridObject()
        void cpp_init(cpp_TypeId typeId, const CppGridLocation &loc)
        void cpp_init(cpp_TypeId typeId, cpp_GridCoord row, cpp_GridCoord col)
        void cpp_init(cpp_TypeId typeId, cpp_GridCoord row, cpp_GridCoord col, cpp_Layer layer)

        #Virtual observation method
        void cpp_obs(cpp_ObsType *observations, const vector[unsigned int] &offsets) const

    #Test implementation for the abstract class
    cdef cppclass CppTestGridObject(CppGridObject):
        CppTestGridObject()
        void cpp_obs(cpp_ObsType *observations, const vector[unsigned int] &offsets) const
        # same method with a dummy parameter to avoid ambiguity resolving
        void cpp_obs(cpp_ObsType *observations, const vector[unsigned int] &offsets, int dummy) const