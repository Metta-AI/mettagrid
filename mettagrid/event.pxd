from libcpp.queue cimport priority_queue
from libcpp.vector cimport vector
from mettagrid.cpp_grid cimport CppGrid
from mettagrid.stats_tracker cimport StatsTracker

from mettagrid.cpp_grid_object cimport cpp_GridObjectId


cdef extern from "event.hpp":
    ctypedef unsigned short EventId
    ctypedef int EventArg
    cdef struct Event:
        unsigned int timestamp
        EventId event_id
        cpp_GridObjectId object_id
        EventArg arg

    cdef cppclass EventManager:
        CppGrid *grid
        StatsTracker *stats
        priority_queue[Event] event_queue
        unsigned int current_timestep
        vector[EventHandler*] event_handlers

        EventManager()

        void init(CppGrid *grid, StatsTracker *stats)

        void schedule_event(
            EventId event_id,
            unsigned int delay,
            cpp_GridObjectId object_id,
            EventArg arg)

        void process_events(unsigned int current_timestep)

    cdef cppclass EventHandler:
        EventManager *event_manager

        EventHandler(EventManager *event_manager)

        void handle_event(cpp_GridObjectId object_id, EventArg arg)
