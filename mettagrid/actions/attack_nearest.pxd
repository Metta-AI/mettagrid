from mettagrid.actions.attack cimport Attack

cdef extern from "attack_nearest.hpp":
    cdef cppclass AttackNearest(Attack):
        pass
