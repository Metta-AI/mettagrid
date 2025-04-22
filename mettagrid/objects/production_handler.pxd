from mettagrid.event cimport EventHandler, EventArg, EventManager
from mettagrid.grid_object cimport cpp_GridObjectId

cdef extern from "production_handler.hpp":
    cdef cppclass ProductionHandler(EventHandler):
        ProductionHandler(EventManager *event_manager)

        void handle_event(cpp_GridObjectId obj_id, EventArg arg)

    cdef cppclass CoolDownHandler(EventHandler):
        CoolDownHandler(EventManager *event_manager)

        void handle_event(cpp_GridObjectId obj_id, EventArg arg)
