from mettagrid.action_handler cimport ActionHandler

cdef extern from "move.hpp":
    cdef cppclass Move(ActionHandler):
        pass
