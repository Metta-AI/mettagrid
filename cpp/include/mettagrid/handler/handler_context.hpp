#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_HANDLER_CONTEXT_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_HANDLER_CONTEXT_HPP_

#include <memory>
#include <random>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "core/game_value_config.hpp"
#include "core/grid.hpp"
#include "core/grid_object.hpp"
#include "core/tag_index.hpp"
#include "core/types.hpp"
#include "handler/handler_config.hpp"
#include "systems/stats_tracker.hpp"

class Agent;
struct GameConfig;

namespace mettagrid {

class AOETracker;
class QuerySystem;

/**
 * HandlerContext holds references to all entities involved in a handler execution
 * and provides entity resolution for filters and mutations.
 *
 * Context varies by handler type:
 *   - on_use: actor=agent performing action, target=object being used
 *   - aoe: actor=source object, target=affected object
 *   - event: actor=target=object being affected
 *   - query filter: actor=original querying entity, target=candidate object
 *   - edge filter: actor=original context actor, source=BFS frontier node, target=candidate
 */
class HandlerContext {
public:
  GridObject* actor = nullptr;
  GridObject* target = nullptr;
  GridObject* source = nullptr;           // BFS frontier node in closure query edge filters
  unsigned int distance = 0;              // Distance from actor to target (set by move line-scan)
  GridLocation target_location = {0, 0};  // Target cell location (set by move line-scan)
  ActionArg move_direction = 0;           // Direction arg from move action (orientation)
  unsigned int timestep = 0;              // Current game timestep (for PeriodicFilter)
  StatsTracker* game_stats = nullptr;     // Game-level stats tracker (for StatsMutation)
  TagIndex* tag_index = nullptr;          // Tag index for tag/query lookups
  Grid* grid = nullptr;                   // Grid for removing objects from cells
  QuerySystem* query_system = nullptr;
  const GameConfig* game_config = nullptr;  // Game config for object type lookups
  AOETracker* aoe_tracker = nullptr;        // AOE tracker for registering/unregistering spawned object AOEs
  std::mt19937* rng = nullptr;
  bool skip_on_update_trigger = false;
  bool mutation_failed = false;  // Set by mutations that fail (e.g. onUse returns false)

  // Optional accumulator for ResourceDeltaMutation on the target entity.
  std::unordered_map<InventoryItem, InventoryDelta>* deferred_target_resource_deltas = nullptr;
  std::vector<InventoryItem>* deferred_target_resource_order = nullptr;
  std::unordered_set<InventoryItem>* deferred_target_resource_seen = nullptr;

  HandlerContext() = default;

  HandlerContext(TagIndex* tag_index,
                 Grid* grid,
                 StatsTracker* game_stats,
                 QuerySystem* query_system,
                 std::mt19937* rng)
      : tag_index(tag_index), grid(grid), game_stats(game_stats), query_system(query_system), rng(rng) {}

  GridObject* resolve(EntityRef ref) const {
    switch (ref) {
      case EntityRef::actor:
        return actor;
      case EntityRef::target:
        return target;
      case EntityRef::source:
        return source;
      default:
        return nullptr;
    }
  }

  HasInventory* resolve_inventory(EntityRef ref) const {
    switch (ref) {
      case EntityRef::actor:
        return actor;
      case EntityRef::target:
        return target;
      case EntityRef::source:
        return source;
      default:
        return nullptr;
    }
  }

  // Get actor's vibe (returns 0 if actor is null)
  ObservationType actor_vibe() const {
    return actor != nullptr ? actor->vibe : 0;
  }

  // Get target's vibe (returns 0 if target is null)
  ObservationType target_vibe() const {
    return target != nullptr ? target->vibe : 0;
  }

  // Resolve a GameValueConfig to its current float value for a given entity
  float resolve_game_value(const GameValueConfig& cfg, EntityRef entity_ref) const;

  // Resolve a stats tracker for a given scope and entity
  StatsTracker* resolve_stats_tracker(GameValueScope scope, GridObject* entity) const;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_HANDLER_CONTEXT_HPP_
