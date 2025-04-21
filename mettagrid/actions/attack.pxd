from libcpp.string cimport string

from mettagrid.action_handler cimport ActionHandler

cdef extern from "attack.hpp":
    cdef cppclass Attack(ActionHandler):
        pass
