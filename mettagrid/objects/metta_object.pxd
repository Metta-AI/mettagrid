from libcpp.string cimport string
from libcpp.map cimport map

from mettagrid.cpp_grid_object cimport CppGridObject

ctypedef map[string, int] ObjectConfig

cdef extern from "metta_object.hpp":
    cdef cppclass MettaObject(CppGridObject):
        unsigned int hp
        void init_mo(ObjectConfig cfg)
        bint has_inventory()
        bint swappable()