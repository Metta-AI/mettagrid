#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_EVENT_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_EVENT_HPP_

#include <memory>
#include <random>
#include <string>
#include <unordered_map>
#include <vector>

#include "handler/filters/filter.hpp"
#include "handler/handler_config.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation.hpp"

namespace mettagrid {

// Forward declarations
class TagIndex;

/**
 * Event processes timestep-based effects through configurable filter and mutation chains.
 *
 * Events fire at specific timesteps and apply mutations to all objects that pass
 * the configured filters. Unlike handlers which are triggered by actions,
 * events are triggered by the game clock.
 *
 * Events are managed by EventScheduler which handles efficient timestep-based scheduling.
 * The Event class itself only handles filter evaluation and mutation application.
 *
 * Usage:
 *   1. Create EventScheduler with event configs
 *   2. Each timestep, call scheduler.process_timestep()
 *   3. EventScheduler applies events directly to matching targets
 */
class Event {
public:
  explicit Event(const EventConfig& config, TagIndex* tag_index = nullptr);

  // Get event name
  const std::string& name() const {
    return _name;
  }

  // Get fallback event name (empty string if none) - used during initialization
  const std::string& fallback_name() const {
    return _fallback_name;
  }

  // Set the fallback event pointer (called by EventScheduler after all events are created)
  void set_fallback_event(Event* fallback) {
    _fallback_event = fallback;
  }

  // Set collectives vector for context-based resolution
  void set_collectives(const std::vector<std::unique_ptr<Collective>>* collectives) {
    _collectives = collectives;
  }

  // Set grid pointer for context-based grid removal
  void set_grid(Grid* grid) {
    _grid = grid;
  }

  // Execute this event: find targets, apply mutations, return number of targets affected.
  // If no targets match and a fallback is set, executes the fallback instead.
  int execute(TagIndex& tag_index, std::mt19937* rng);

  // Try to apply this event to the given target (no actor for events)
  // Returns true if all filters passed and mutations were applied
  bool try_apply(HasInventory* target);

  // Check if all filters pass without applying mutations
  bool check_filters(HasInventory* target) const;

private:
  std::string _name;
  int _target_tag_id = -1;           // Tag ID for finding targets (required)
  int _max_targets = 0;              // 0 = unlimited
  std::string _fallback_name;        // Fallback event name (for initialization)
  Event* _fallback_event = nullptr;  // Pointer to fallback event (resolved at init)
  TagIndex* _tag_index = nullptr;    // Tag index for NearFilter lookups
  Grid* _grid = nullptr;             // Grid for removing objects from cells
  const std::vector<std::unique_ptr<Collective>>* _collectives = nullptr;  // Collectives for context lookup
  std::vector<std::unique_ptr<Filter>> _filters;
  std::vector<std::unique_ptr<Mutation>> _mutations;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_EVENT_HPP_
