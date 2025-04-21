from mettagrid.action_handler cimport ActionHandler

cdef extern from "change_color.hpp":
    cdef cppclass ChangeColorAction(ActionHandler):
        pass
