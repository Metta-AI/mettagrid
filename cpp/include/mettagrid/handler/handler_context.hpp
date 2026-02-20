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
#include "handler/handler_config.hpp"
#include "objects/collective.hpp"
#include "systems/stats_tracker.hpp"

class Agent;

namespace mettagrid {

class QuerySystem;

/**
 * HandlerContext holds references to all entities involved in a handler execution
 * and provides entity resolution for filters and mutations.
 *
 * Context varies by handler type:
 *   - on_use: actor=agent performing action, target=object being used
 *   - aoe: actor=source object, target=affected object
 *   - event: actor=target=object being affected
 */
class HandlerContext {
public:
  GridObject* actor = nullptr;
  GridObject* target = nullptr;
  StatsTracker* game_stats = nullptr;  // Game-level stats tracker (for StatsMutation)
  TagIndex* tag_index = nullptr;       // Tag index for tag/query lookups
  Grid* grid = nullptr;                // Grid for removing objects from cells
  const std::vector<std::unique_ptr<Collective>>* collectives = nullptr;  // Collectives indexed by ID (for events)
  QuerySystem* query_system = nullptr;                                    // For RecomputeMaterializedQueryMutation
  std::mt19937* rng = nullptr;                                            // Random number generator
  bool skip_on_update_trigger = false;  // Skip triggering on_update handlers (prevent recursion)

  // Optional accumulator for ResourceDeltaMutation on the target entity.
  // Used to apply a single net resource delta after evaluating multiple effects (e.g., fixed AOEs),
  // avoiding intermediate clamp artifacts.
  std::unordered_map<InventoryItem, InventoryDelta>* deferred_target_resource_deltas = nullptr;
  std::vector<InventoryItem>* deferred_target_resource_order = nullptr;
  std::unordered_set<InventoryItem>* deferred_target_resource_seen = nullptr;

  HandlerContext() = default;

  // Construct with all system-level pointers (set once in MettaGrid)
  HandlerContext(TagIndex* tag_index,
                 Grid* grid,
                 StatsTracker* game_stats,
                 const std::vector<std::unique_ptr<Collective>>* collectives,
                 QuerySystem* query_system,
                 std::mt19937* rng)
      : tag_index(tag_index),
        grid(grid),
        game_stats(game_stats),
        collectives(collectives),
        query_system(query_system),
        rng(rng) {}

  // Resolve an EntityRef to the corresponding GridObject*
  // Returns nullptr for collective refs (Collective is not a GridObject)
  GridObject* resolve(EntityRef ref) const {
    switch (ref) {
      case EntityRef::actor:
        return actor;
      case EntityRef::target:
        return target;
      case EntityRef::actor_collective:
        return nullptr;
      case EntityRef::target_collective:
        return nullptr;
      default:
        return nullptr;
    }
  }

  // Resolve an EntityRef to a HasInventory* (handles both GridObject and Collective refs)
  HasInventory* resolve_inventory(EntityRef ref) const {
    switch (ref) {
      case EntityRef::actor:
        return actor;
      case EntityRef::target:
        return target;
      case EntityRef::actor_collective:
        return get_collective(actor);
      case EntityRef::target_collective:
        return get_collective(target);
      default:
        return nullptr;
    }
  }

  // Get the collective for an entity
  Collective* get_collective(GridObject* entity) const {
    if (entity == nullptr) {
      return nullptr;
    }
    return entity->getCollective();
  }

  // Get actor's collective
  Collective* actor_collective() const {
    return get_collective(actor);
  }

  // Get target's collective
  Collective* target_collective() const {
    return get_collective(target);
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

  // Look up a collective by ID (returns nullptr if not found)
  Collective* get_collective_by_id(int collective_id) const {
    if (collectives == nullptr || collective_id < 0 || static_cast<size_t>(collective_id) >= collectives->size()) {
      return nullptr;
    }
    return (*collectives)[collective_id].get();
  }
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_HANDLER_CONTEXT_HPP_
