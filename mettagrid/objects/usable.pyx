# distutils: language=c++

from mettagrid.objects.metta_object cimport MettaObject#, ObjectConfig
from mettagrid.objects.agent cimport Agent

cdef cppclass Usable(MettaObject):
    # void init_usable():
    #     this.ready = 1

    bint usable(const Agent *actor):
        return this.ready and this.use_cost <= actor.energy