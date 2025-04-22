from mettagrid.actions.attack cimport Attack
from mettagrid.cpp_action_handler cimport cpp_ActionConfig

cdef extern from "attack_nearest.hpp":
    cdef cppclass AttackNearest(Attack):
        AttackNearest(const cpp_ActionConfig& cfg)
