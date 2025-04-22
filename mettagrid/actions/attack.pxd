from mettagrid.cpp_action_handler cimport CppActionHandler, cpp_ActionConfig

cdef extern from "attack.hpp":
    cdef cppclass Attack(CppActionHandler):
        Attack(const cpp_ActionConfig& cfg)
