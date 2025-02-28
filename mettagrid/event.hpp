#ifndef EVENT_H
#define EVENT_H

#include <queue>
#include <vector>
using namespace std;

#include "grid_object.hpp"
#include "stats_tracker.hpp"
#include "grid.hpp"
typedef unsigned short EventId;
typedef int EventArg;
struct Event {
    unsigned int timestamp;
    EventId event_id;
    GridObjectId object_id;
    EventArg arg;

    bool operator<(const Event& other) const {
        return timestamp > other.timestamp;
    }
};

class EventManager {
private:
    vector<EventHandler*> _event_handlers;
    priority_queue<Event> _event_queue;
    Grid* _grid;
    StatsTracker* _stats;
    unsigned int _current_timestep;

public:
    EventManager(vector<EventHandler*> event_handlers) {
        this->_event_handlers = event_handlers;
        for (size_t idx = 0; idx < event_handlers.size(); idx++) {
            this->_event_handlers[idx]->init(this, idx);
        }
        this->_current_timestep = 0;
    }

    void schedule_event(EventId event_id, unsigned int delay, GridObjectId object_id, EventArg arg) {
        Event event;
        event.timestamp = this->_current_timestep + delay;
        event.event_id = event_id;
        event.object_id = object_id;
        event.arg = arg;
        this->_event_queue.push(event);
    }

    void init(Grid* grid, StatsTracker* stats) {
        this->_grid = grid;
        this->_stats = stats;
    }

    void process_events(unsigned int current_timestep) {
        this->_current_timestep = current_timestep;
        Event event;
        while (!this->_event_queue.empty()) {
            event = this->_event_queue.top();
            if (event.timestamp > this->_current_timestep) {
                break;
            }
            this->_event_queue.pop();
            this->_event_handlers[event.event_id]->handle_event(event.object_id, event.arg);
        }
    }
};

class EventHandler {
protected:
    EventManager* event_manager;
    EventId event_id;

public:
    // xcxc understand virtual destructor
    virtual ~EventHandler() {}

    void init(EventManager* em, EventId eid) {
        event_manager = em;
        event_id = eid;
    }

    void schedule(unsigned int delay, GridObjectId object_id, EventArg arg) {
        event_manager->schedule_event(event_id, delay, object_id, arg);
    }

    virtual void handle_event(GridObjectId object_id, int arg) {}
};


#endif // EVENT_H
