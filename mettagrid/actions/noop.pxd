from mettagrid.cpp_action_handler cimport CppActionHandler, cpp_ActionConfig

cdef extern from "noop.hpp":
    cdef cppclass Noop(CppActionHandler):
        Noop(const cpp_ActionConfig& cfg)
