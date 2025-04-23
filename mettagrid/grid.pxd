from mettagrid.cpp_grid cimport CppGrid
from mettagrid.cpp_grid_object cimport CppGridObject, cpp_GridObjectId, CppGridLocation, cpp_GridCoord, cpp_TypeId, cpp_Layer, cpp_Orientation

cdef class Grid:
    cdef CppGrid* _impl

    # Changed to cdef for methods with C++ parameters
    cdef bint add_object(self, CppGridObject* obj)
    cdef void remove_object(self, CppGridObject* obj)
    cpdef void remove_object_by_id(self, cpp_GridObjectId id)
    cdef bint move_object(self, cpp_GridObjectId id, CppGridLocation loc)
    cpdef void swap_objects(self, cpp_GridObjectId id1, cpp_GridObjectId id2)

    cdef CppGridObject* object(self, cpp_GridObjectId id)
    cdef CppGridObject* object_at(self, CppGridLocation loc)
    cdef CppGridObject* object_at_with_type(self, CppGridLocation loc, cpp_TypeId type_id)
    cdef CppGridObject* object_at_coords(self, cpp_GridCoord r, cpp_GridCoord c, cpp_TypeId type_id)

    cdef CppGridLocation location(self, cpp_GridObjectId id)
    cdef CppGridLocation relative_location(self, CppGridLocation loc, cpp_Orientation orientation, cpp_GridCoord distance=*, cpp_GridCoord offset=*)
    cdef CppGridLocation relative_location_with_type(self, CppGridLocation loc, cpp_Orientation orientation, cpp_TypeId type_id)
    cdef CppGridLocation relative_location_full(self, CppGridLocation loc, cpp_Orientation orientation, cpp_GridCoord distance, cpp_GridCoord offset, cpp_TypeId type_id)

    cpdef bint is_empty(self, unsigned int row, unsigned int col)
    cpdef bint add_object_from_ptr(self, unsigned long ptr_value)

