from mettagrid.cpp_action_handler cimport CppActionHandler, cpp_ActionConfig

cdef extern from "swap.hpp":
    cdef cppclass Swap(CppActionHandler):
        Swap(const cpp_ActionConfig& cfg)
