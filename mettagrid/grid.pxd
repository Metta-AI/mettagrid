# distutils: language=c++

from libcpp.vector cimport vector

# Import the C++ types from cpp_grid_object.pxd, not grid_object.pxd
from mettagrid.cpp_grid_object cimport cpp_Layer, cpp_TypeId, cpp_GridObjectId
from mettagrid.cpp_grid_object cimport CppGridObject, CppGridLocation, cpp_Orientation, cpp_GridCoord

cdef extern from "grid.hpp":
    cdef cppclass Grid:
        unsigned int width
        unsigned int height
        cpp_Layer num_layers

        vector[vector[vector[int]]] grid
        vector[CppGridObject*] objects

        Grid(unsigned int width, unsigned int height, vector[cpp_Layer] layer_for_type_id)
        void __dealloc__()

        const CppGridLocation location(cpp_GridObjectId id)
        const CppGridLocation location(unsigned int r, unsigned int c, cpp_Layer layer)
        const CppGridLocation relative_location(
            const CppGridLocation &loc, cpp_Orientation orientation,
            cpp_GridCoord distance, cpp_GridCoord offset)
        const CppGridLocation relative_location(
            const CppGridLocation &loc, cpp_Orientation orientation)
        const CppGridLocation relative_location(
            const CppGridLocation &loc, cpp_Orientation orientation, cpp_TypeId type_id)
        const CppGridLocation relative_location(
            const CppGridLocation &loc, cpp_Orientation orientation,
            cpp_GridCoord distance, cpp_GridCoord offset, cpp_TypeId type_id)

        char is_empty(unsigned int r, unsigned int c)

        char add_object(CppGridObject *obj)
        void remove_object(CppGridObject *obj)
        void remove_object(cpp_GridObjectId id)
        bint move_object(cpp_GridObjectId id, const CppGridLocation &loc)
        void swap_objects(cpp_GridObjectId id1, cpp_GridObjectId id2)
        CppGridObject* object(cpp_GridObjectId obj_id)
        CppGridObject* object_at(const CppGridLocation &loc)
        CppGridObject* object_at(const CppGridLocation &loc, cpp_TypeId type_id)
        CppGridObject* object_at(cpp_GridCoord r, cpp_GridCoord c, cpp_TypeId type_id)
