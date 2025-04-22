from mettagrid.cpp_action_handler cimport CppActionHandler, cpp_ActionConfig

cdef extern from "get_output.hpp":
    cdef cppclass GetOutput(CppActionHandler):
        GetOutput(const cpp_ActionConfig& cfg)
