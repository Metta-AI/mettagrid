from mettagrid.grid_object cimport GridCoord
from .metta_object cimport ObjectConfig
from .converter cimport Converter

cdef extern from "altar.hpp":
    cdef cppclass Altar(Converter):
        Altar(GridCoord r, GridCoord c, ObjectConfig cfg) except +
