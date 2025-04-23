from libcpp.vector cimport vector
import numpy as np
cimport numpy as np

from mettagrid.cpp_grid_object cimport (
    CppGridLocation,
    CppGridObject,
    CppTestGridObject,
    cpp_TypeId,
    cpp_GridObjectId,
    cpp_GridCoord,
    cpp_Layer,
    cpp_ObsType,
    cpp_Orientation
)

cdef class GridLocation:
    cdef CppGridLocation _cpp_loc
    cdef unsigned int row(self)
    cdef void set_row(self, unsigned int value)
    cdef unsigned int col(self)
    cdef void set_col(self, unsigned int value)
    cdef unsigned short layer(self)
    cdef void set_layer(self, unsigned short value)

cdef class GridObject:
    cdef CppGridObject* _cpp_obj
    cdef bint _owns_ptr

    cpdef void init(self, unsigned short type_id, object location_or_row, object col=?, object layer=?)
    cpdef unsigned int id(self)
    cpdef void set_id(self, unsigned int value)
    cpdef cpp_TypeId type_id(self)
    cpdef GridLocation location(self)
    cpdef void set_location(self, GridLocation loc)
    cpdef void obs(self, np.ndarray[unsigned char, ndim=1] obs_array, list offsets)

cdef class TestGridObject(GridObject):
    cpdef void obs(self, np.ndarray[unsigned char, ndim=1] obs_array, list offsets)