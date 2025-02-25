from libcpp.vector cimport vector
from libcpp.string cimport string
from mettagrid.grid_object cimport GridCoord
from mettagrid.objects.usable cimport Usable
from mettagrid.objects.metta_object cimport ObjectConfig
from mettagrid.observation_encoder cimport ObsType

cdef extern from "armory.hpp":
    cdef cppclass Armory(Usable):
        Armory(GridCoord r, GridCoord c, ObjectConfig cfg) except +

        void obs(ObsType *obs)

        @staticmethod
        vector[string] feature_names()
