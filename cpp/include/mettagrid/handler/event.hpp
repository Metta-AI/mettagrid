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
  explicit Event(const EventConfig& config);

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

  // Execute this event: find targets, apply mutations, return number of targets affected.
  // If no targets match and a fallback is set, executes the fallback instead.
  int execute(const HandlerContext& ctx);

  // Try to apply this event to the given target (events use actor == target)
  // Returns true if all filters passed and mutations were applied
  bool try_apply(GridObject* target, const HandlerContext& ctx);

  // Check if all filters pass without applying mutations
  bool check_filters(GridObject* target, const HandlerContext& ctx) const;

private:
  std::string _name;
  std::shared_ptr<QueryConfig> _target_query;  // Query for finding targets (required)
  int _max_targets = 0;                        // 0 = unlimited
  std::string _fallback_name;                  // Fallback event name (for initialization)
  Event* _fallback_event = nullptr;            // Pointer to fallback event (resolved at init)
  std::vector<std::unique_ptr<Filter>> _filters;
  std::vector<std::unique_ptr<Mutation>> _mutations;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_EVENT_HPP_
