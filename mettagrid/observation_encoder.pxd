from libcpp.vector cimport vector
from libcpp.string cimport string

from mettagrid.cpp_grid_object cimport cpp_GridObjectId, cpp_ObsType, CppGridObject

cdef class ObservationEncoder:
    cdef:
        unsigned int _obs_width
        unsigned int _obs_height
        vector[vector[unsigned int]] _offsets
        vector[string] _feature_names
        vector[vector[string]] _type_feature_names
    
    cdef init(self, unsigned int obs_width, unsigned int obs_height)
    cdef encode(self, CppGridObject *obj, cpp_ObsType[:] obs)
    cdef _encode(self, CppGridObject *obj, cpp_ObsType[:] obs, vector[unsigned int] offsets)
    cdef vector[string] feature_names(self)
    cpdef observation_space(self)
    cpdef obs_np_type(self)

cdef class SemiCompactObservationEncoder(ObservationEncoder):
    pass

