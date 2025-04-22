from mettagrid.cpp_action_handler cimport CppActionHandler, cpp_ActionConfig

cdef extern from "change_color.hpp":
    cdef cppclass ChangeColorAction(CppActionHandler):
        ChangeColorAction(const cpp_ActionConfig& cfg)
