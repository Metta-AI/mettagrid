from mettagrid.action_handler cimport ActionHandler

cdef extern from "swap.hpp":
    cdef cppclass Swap(ActionHandler):
        pass
