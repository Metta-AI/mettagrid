from libcpp.queue cimport priority_queue
from libcpp.vector cimport vector
from mettagrid.grid_object cimport GridObjectId
from mettagrid.grid cimport Grid
from mettagrid.stats_tracker cimport StatsTracker

cdef extern from "event.hpp":
    ctypedef unsigned short EventId
    ctypedef int EventArg
    cdef struct Event:
        unsigned int timestamp
        EventId event_id
        GridObjectId object_id
        EventArg arg

    cdef class EventManager:
        cdef:
            Grid *_grid
            StatsTracker *_stats
            priority_queue[Event] _event_queue
            unsigned int _current_timestep
            list[EventHandler] _event_handlers

        cdef void init(self, Grid *grid, StatsTracker *stats)

        cdef void schedule_event(
            self,
            EventId event_id,
            unsigned int delay,
            GridObjectId object_id,
            EventArg arg)

        cdef void process_events(self, unsigned int current_timestep)

    cdef class EventHandler:
        cdef EventManager event_manager
        cdef EventId event_id

        cdef void init(self, EventManager event_manager, EventId event_id)
        cdef void schedule(self, unsigned int delay, GridObjectId object_id, EventArg arg)
        cdef void handle_event(self, GridObjectId object_id, int arg)
