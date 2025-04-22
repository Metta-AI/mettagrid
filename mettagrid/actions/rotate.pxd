from mettagrid.cpp_action_handler cimport CppActionHandler, cpp_ActionConfig

cdef extern from "rotate.hpp":
    cdef cppclass Rotate(CppActionHandler):
        Rotate(const cpp_ActionConfig& cfg)
