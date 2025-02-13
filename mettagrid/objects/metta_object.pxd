# distutils: language=c++

from mettagrid.grid_object cimport GridObject
from libcpp.string cimport string
from libcpp.map cimport map

ctypedef map[string, int] ObjectConfig

cdef cppclass MettaObject(GridObject):
    unsigned int hp

    void init_mo(ObjectConfig cfg)

    bint is_usable_type()