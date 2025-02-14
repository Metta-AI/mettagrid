from mettagrid.objects.metta_object cimport MettaObject, ObjectConfig
from mettagrid.objects.agent cimport Agent

cdef cppclass Usable(MettaObject):
    unsigned int use_cost
    unsigned int cooldown
    unsigned char ready

    inline void init_usable(ObjectConfig cfg):
        this.ready = 1
        this.use_cost = cfg[b"use_cost"]
        this.cooldown = cfg[b"cooldown"]

    inline bint usable(const Agent *actor):
        return this.ready and this.use_cost <= actor.energy
