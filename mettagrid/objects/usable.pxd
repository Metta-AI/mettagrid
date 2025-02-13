# distutils: language=c++

from mettagrid.objects.metta_object cimport MettaObject#, ObjectConfig
from mettagrid.objects.agent cimport Agent

from libcpp.string cimport string
from libcpp.map cimport map

ctypedef map[string, int] ObjectConfig

cdef cppclass Usable(MettaObject):
    unsigned int use_cost
    unsigned int cooldown
    unsigned char ready

    bint usable(const Agent *actor)
