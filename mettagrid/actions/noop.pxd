from mettagrid.action_handler cimport ActionHandler

cdef extern from "noop.hpp":
    cdef cppclass Noop(ActionHandler):
        pass
