from mettagrid.grid_object cimport GridCoord
from mettagrid.objects.metta_object cimport ObjectConfig
from mettagrid.objects.converter cimport Converter

cdef extern from "mine.hpp":
    cdef cppclass Mine(Converter):
        Mine(GridCoord r, GridCoord c, ObjectConfig cfg) except +
