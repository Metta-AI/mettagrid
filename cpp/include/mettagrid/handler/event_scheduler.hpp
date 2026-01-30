#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_EVENT_SCHEDULER_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_EVENT_SCHEDULER_HPP_

#include <algorithm>
#include <map>
#include <memory>
#include <random>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include "core/tag_index.hpp"
#include "handler/event.hpp"
#include "handler/filters/filter.hpp"
#include "handler/handler_config.hpp"
#include "objects/collective.hpp"

// Forward declarations
class Collective;
class Grid;

namespace mettagrid {

/**
 * EventScheduler efficiently manages event firing by maintaining a sorted schedule.
 *
 * Instead of checking every event on every timestep, this class pre-computes
 * a sorted list of (timestep, event*) pairs and maintains a pointer to the next
 * scheduled event. This provides O(1) per-timestep cost when no events fire,
 * and O(k) cost when k events fire at the current timestep.
 *
 * Usage:
 *   1. Create scheduler with map of EventConfigs
 *   2. Each timestep, call process_timestep() with a function to get targets
 *   3. Events are applied directly to matching targets
 */
class EventScheduler {
public:
  // Constructor that takes events, RNG for random target selection, and optional tag index
  EventScheduler(const std::map<std::string, EventConfig>& event_configs,
                 std::mt19937* rng,
                 TagIndex* tag_index = nullptr);

  // Process all events scheduled for this timestep
  // For each event that fires, uses TagIndex to efficiently get candidate targets,
  // then applies the event to each target that passes its filters.
  // Returns the number of events that fired.
  int process_timestep(int timestep, TagIndex& tag_index);

  // Get event by name (for stats logging, etc.)
  Event* get_event(const std::string& name);

  // Set collectives vector for context-based resolution in all events
  void set_collectives(const std::vector<std::unique_ptr<Collective>>* collectives);

  // Set grid pointer for context-based grid removal in all events
  void set_grid(Grid* grid);

  // Check if there are any events scheduled
  bool has_events() const {
    return !_schedule.empty();
  }

  // Get total number of scheduled event firings
  size_t schedule_size() const {
    return _schedule.size();
  }

private:
  // Owned events, keyed by name
  std::map<std::string, std::unique_ptr<Event>> _events;

  // Sorted schedule of (timestep, event*) pairs
  std::vector<std::pair<int, Event*>> _schedule;

  // Index of next event in schedule
  size_t _next_idx = 0;

  // Random number generator for random target selection
  std::mt19937* _rng{nullptr};
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_EVENT_SCHEDULER_HPP_
