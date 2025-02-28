from mettagrid.event cimport EventHandler, EventArg
from mettagrid.grid_object cimport GridObjectId
from .constants cimport ObjectTypeNames, Events
from .converter cimport Converter

cdef class ProductionHandler(EventHandler):
    cdef inline void handle_event(self, GridObjectId obj_id, EventArg arg):
        cdef Converter *converter = <Converter*>self.event_manager._grid.object(obj_id)
        if converter is NULL:
            return

        converter.finish_converting()
        self.event_manager._stats.incr(ObjectTypeNames[converter._type_id], b"produced")

        if converter.maybe_start_converting():
            self.event_manager.schedule_event(Events.FinishConverting, converter.recipe_duration, converter.id, 0)
