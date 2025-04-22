from mettagrid.cpp_action_handler cimport CppActionHandler, cpp_ActionConfig

cdef extern from "move.hpp":
    cdef cppclass Move(CppActionHandler):
        Move(const cpp_ActionConfig& cfg)
