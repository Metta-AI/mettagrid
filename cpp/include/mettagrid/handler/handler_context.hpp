#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_HANDLER_CONTEXT_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_HANDLER_CONTEXT_HPP_

#include <memory>
#include <string>
#include <vector>

#include "core/game_value_config.hpp"
#include "core/grid.hpp"
#include "core/grid_object.hpp"
#include "core/tag_index.hpp"
#include "handler/handler_config.hpp"
#include "objects/collective.hpp"
#include "objects/has_inventory.hpp"
#include "systems/stats_tracker.hpp"

class Agent;

namespace mettagrid {

/**
 * HandlerContext holds references to all entities involved in a handler execution
 * and provides entity resolution for filters and mutations.
 *
 * Context varies by handler type:
 *   - on_use: actor=agent performing action, target=object being used
 *   - aoe: actor=source object, target=affected object
 *   - event: actor=nullptr, target=object being affected
 */
class HandlerContext {
public:
  HasInventory* actor = nullptr;
  HasInventory* target = nullptr;
  StatsTracker* game_stats = nullptr;  // Game-level stats tracker (for StatsMutation)
  TagIndex* tag_index = nullptr;       // Tag index for NearFilter lookups
  Grid* grid = nullptr;                // Grid for removing objects from cells
  const std::vector<std::unique_ptr<Collective>>* collectives = nullptr;  // Collectives indexed by ID (for events)
  bool skip_on_update_trigger = false;  // Skip triggering on_update handlers (prevent recursion)

  HandlerContext() = default;
  HandlerContext(HasInventory* act, HasInventory* tgt, bool skip_update = false)
      : actor(act), target(tgt), skip_on_update_trigger(skip_update) {}
  HandlerContext(HasInventory* act, HasInventory* tgt, StatsTracker* stats, bool skip_update = false)
      : actor(act), target(tgt), game_stats(stats), skip_on_update_trigger(skip_update) {}
  HandlerContext(HasInventory* act, HasInventory* tgt, StatsTracker* stats, TagIndex* tags, bool skip_update = false)
      : actor(act), target(tgt), game_stats(stats), tag_index(tags), skip_on_update_trigger(skip_update) {}
  HandlerContext(HasInventory* act,
                 HasInventory* tgt,
                 StatsTracker* stats,
                 TagIndex* tags,
                 const std::vector<std::unique_ptr<Collective>>* colls,
                 bool skip_update = false)
      : actor(act),
        target(tgt),
        game_stats(stats),
        tag_index(tags),
        collectives(colls),
        skip_on_update_trigger(skip_update) {}

  // Resolve an EntityRef to the corresponding HasInventory*
  HasInventory* resolve(EntityRef ref) const {
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

  // Get GridObject for an entity (if it's a GridObject)
  GridObject* get_grid_object(HasInventory* entity) const {
    return dynamic_cast<GridObject*>(entity);
  }

  // Get the collective for an entity (if it's a GridObject)
  Collective* get_collective(HasInventory* entity) const {
    GridObject* grid_obj = get_grid_object(entity);
    if (grid_obj == nullptr) {
      return nullptr;
    }
    return grid_obj->getCollective();
  }

  // Get actor's collective
  Collective* actor_collective() const {
    return get_collective(actor);
  }

  // Get target's collective
  Collective* target_collective() const {
    return get_collective(target);
  }

  // Get actor as GridObject (for vibe access, etc.)
  GridObject* actor_grid_object() const {
    return get_grid_object(actor);
  }

  // Get target as GridObject (for vibe access, etc.)
  GridObject* target_grid_object() const {
    return get_grid_object(target);
  }

  // Get actor's vibe (returns 0 if actor is not a GridObject)
  ObservationType actor_vibe() const {
    GridObject* grid_obj = actor_grid_object();
    return grid_obj != nullptr ? grid_obj->vibe : 0;
  }

  // Get target's vibe (returns 0 if target is not a GridObject)
  ObservationType target_vibe() const {
    GridObject* grid_obj = target_grid_object();
    return grid_obj != nullptr ? grid_obj->vibe : 0;
  }

  // Resolve a GameValueConfig to its current float value for a given entity
  float resolve_game_value(const GameValueConfig& cfg, EntityRef entity_ref) const;

  // Resolve a stats tracker for a given scope and entity
  StatsTracker* resolve_stats_tracker(GameValueScope scope, HasInventory* entity) const;

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
