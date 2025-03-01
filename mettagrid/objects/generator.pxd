from libcpp.vector cimport vector
from libcpp.string cimport string
from mettagrid.grid_object cimport GridCoord
from mettagrid.event cimport EventManager
from .metta_object cimport ObjectConfig
from .converter cimport Converter

cdef extern from "generator.hpp":
    cdef cppclass Generator(Converter):
        Generator(GridCoord r, GridCoord c, ObjectConfig cfg, EventManager *event_manager) except +

        @staticmethod
        vector[string] feature_names()
