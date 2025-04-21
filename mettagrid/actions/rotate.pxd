from mettagrid.action_handler cimport ActionHandler

cdef extern from "rotate.hpp":
    cdef cppclass Rotate(ActionHandler):
        pass
