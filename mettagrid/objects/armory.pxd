from mettagrid.grid_object cimport GridCoord
from mettagrid.objects.metta_object cimport ObjectConfig
from mettagrid.objects.converter cimport Converter

cdef extern from "armory.hpp":
    cdef cppclass Armory(Converter):
        Armory(GridCoord r, GridCoord c, ObjectConfig cfg) except +
