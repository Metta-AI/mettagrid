#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_HANDLER_CONFIG_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_HANDLER_CONFIG_HPP_

#include <string>
#include <vector>

#include "core/filter_config.hpp"
#include "core/mutation_config.hpp"

namespace mettagrid {

// Handler dispatch mode for MultiHandler
enum class HandlerMode {
  FirstMatch,  // Return on first handler that applies (for on_use)
  All          // Apply all handlers that match filters (for AOE)
};

// ============================================================================
// Handler Config
// ============================================================================

struct HandlerConfig {
  std::string name;
  std::vector<FilterConfig> filters;      // All must pass for handler to trigger
  std::vector<MutationConfig> mutations;  // Applied sequentially if filters pass

  HandlerConfig() = default;
  explicit HandlerConfig(const std::string& handler_name) : name(handler_name) {}
};

// ============================================================================
// AOE Config - Unified configuration for Area of Effect systems
// ============================================================================

// Resource delta for presence_deltas (applied on enter/exit)
struct ResourceDelta {
  InventoryItem resource_id = 0;
  InventoryDelta delta = 0;
};

/**
 * AOEConfig - Configuration for Area of Effect (AOE) systems.
 *
 * Inherits filters and mutations from HandlerConfig.
 *
 * Supports two modes:
 * - Static (is_static=true, default): Pre-computed cell registration for efficiency.
 *   Good for stationary objects like turrets, healing stations.
 * - Mobile (is_static=false): Re-evaluated each tick for moving sources.
 *   Good for agents with auras.
 *
 * In AOE context, "actor" refers to the AOE source object and "target" refers to
 * the affected object.
 */
struct AOEConfig : public HandlerConfig {
  int radius = 1;            // Euclidean distance for AOE
  bool is_static = true;     // true = fixed (default), false = mobile (for agents)
  bool effect_self = false;  // Whether source is affected by its own AOE

  // One-time resource changes when target enters/exits AOE
  // Enter: apply +delta, Exit: apply -delta
  std::vector<ResourceDelta> presence_deltas;
};

// ============================================================================
// Event Config - Timestep-based events
// ============================================================================

/**
 * EventConfig - Configuration for timestep-based events.
 *
 * Events fire at specified timesteps and apply mutations to all objects
 * that pass the configured filters. Unlike handlers (triggered by actions)
 * or AOE (triggered by proximity), events are triggered by the game clock.
 */
struct EventConfig {
  std::string name;                       // Unique name for this event
  int target_tag_id = -1;                 // Tag ID for finding targets via TagIndex (required)
  std::vector<int> timesteps;             // Timesteps when this event fires
  std::vector<FilterConfig> filters;      // All must pass for event to affect object
  std::vector<MutationConfig> mutations;  // Applied to matching objects
  int max_targets = 0;                    // Maximum targets to apply to (0 = unlimited)
  std::string fallback;                   // Event name to fire if no targets match (optional)

  EventConfig() = default;
  explicit EventConfig(const std::string& event_name) : name(event_name) {}
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_HANDLER_CONFIG_HPP_
