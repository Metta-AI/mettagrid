from mettagrid.action_handler cimport ActionHandler

cdef extern from "get_output.hpp":
    cdef cppclass GetOutput(ActionHandler):
        pass
