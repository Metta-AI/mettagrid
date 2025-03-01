from libcpp.vector cimport vector
from libcpp.string cimport string
from mettagrid.event cimport EventManager
from mettagrid.grid_object cimport GridCoord
from mettagrid.objects.metta_object cimport ObjectConfig
from mettagrid.objects.converter cimport Converter

cdef extern from "armory.hpp":
    cdef cppclass Armory(Converter):
        Armory(GridCoord r, GridCoord c, ObjectConfig cfg, EventManager *event_manager) except +

        @staticmethod
        vector[string] feature_names()
