#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_EVENT_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_EVENT_HPP_

#include <memory>
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

  // Get target tag ID for efficient lookup via TagIndex (required)
  int target_tag_id() const {
    return _target_tag_id;
  }

  // Get max targets (0 = unlimited)
  int max_targets() const {
    return _max_targets;
  }

  // Set collectives vector for context-based resolution
  void set_collectives(const std::vector<std::unique_ptr<Collective>>* collectives) {
    _collectives = collectives;
  }

  // Try to apply this event to the given target (no actor for events)
  // Returns true if all filters passed and mutations were applied
  bool try_apply(HasInventory* target);

  // Check if all filters pass without applying mutations
  bool check_filters(HasInventory* target) const;

  // Accessor for EventScheduler pre-filtering
  const std::vector<std::unique_ptr<Filter>>& get_filters() const {
    return _filters;
  }

private:
  std::string _name;
  int _target_tag_id = -1;                                                 // Tag ID for finding targets (required)
  int _max_targets = 0;                                                    // 0 = unlimited
  TagIndex* _tag_index = nullptr;                                          // Tag index for NearFilter lookups
  const std::vector<std::unique_ptr<Collective>>* _collectives = nullptr;  // Collectives for context lookup
  std::vector<std::unique_ptr<Filter>> _filters;
  std::vector<std::unique_ptr<Mutation>> _mutations;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_EVENT_HPP_
