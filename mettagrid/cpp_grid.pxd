# cpp_grid.pxd
from libcpp.vector cimport vector
from mettagrid.cpp_grid_object cimport CppGridObject, cpp_GridObjectId, CppGridLocation, cpp_GridCoord, cpp_Layer, cpp_TypeId, cpp_Orientation

cdef extern from "cpp_grid.hpp":
    cdef cppclass CppGrid:
        unsigned int width
        unsigned int height
        vector[cpp_Layer] layer_for_type_id
        cpp_Layer num_layers
        vector[vector[vector[cpp_GridObjectId]]] grid
        vector[CppGridObject*] objects

        CppGrid(unsigned int width, unsigned int height, vector[cpp_Layer] layer_for_type_id)
        void __dealloc__()

        char add_object(CppGridObject* obj)
        void remove_object(CppGridObject* obj)
        void remove_object(cpp_GridObjectId id)
        char move_object(cpp_GridObjectId id, const CppGridLocation& loc)
        void swap_objects(cpp_GridObjectId id1, cpp_GridObjectId id2)

        CppGridObject* object(cpp_GridObjectId obj_id)
        CppGridObject* object_at(const CppGridLocation& loc)
        CppGridObject* object_at(const CppGridLocation& loc, cpp_TypeId type_id)
        CppGridObject* object_at(cpp_GridCoord r, cpp_GridCoord c, cpp_TypeId type_id)

        CppGridLocation location(cpp_GridObjectId id)
        CppGridLocation relative_location(const CppGridLocation& loc, cpp_Orientation orientation, cpp_GridCoord distance, cpp_GridCoord offset)
        CppGridLocation relative_location(const CppGridLocation& loc, cpp_Orientation orientation, cpp_GridCoord distance, cpp_GridCoord offset, cpp_TypeId type_id)
        CppGridLocation relative_location(const CppGridLocation& loc, cpp_Orientation orientation)
        CppGridLocation relative_location(const CppGridLocation& loc, cpp_Orientation orientation, cpp_TypeId type_id)

        char is_empty(unsigned int row, unsigned int col)
