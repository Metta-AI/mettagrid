#include "handler/handler_context.hpp"

#include "objects/agent.hpp"

namespace mettagrid {

float HandlerContext::resolve_game_value(const GameValueConfig& cfg, EntityRef entity_ref) const {
  HasInventory* entity = resolve(entity_ref);

  switch (cfg.type) {
    case GameValueType::INVENTORY: {
      if (entity == nullptr) return 0.0f;
      return static_cast<float>(entity->inventory.amount(cfg.id));
    }
    case GameValueType::STAT: {
      StatsTracker* tracker = resolve_stats_tracker(cfg.scope, entity);
      if (tracker == nullptr) return 0.0f;
      if (!cfg.stat_name.empty()) {
        return tracker->get(cfg.stat_name);
      }
      return *tracker->get_ptr(cfg.id);
    }
    case GameValueType::TAG_COUNT: {
      if (tag_index == nullptr) return 0.0f;
      return static_cast<float>(tag_index->count_objects_with_tag(cfg.id));
    }
  }
  return 0.0f;
}

StatsTracker* HandlerContext::resolve_stats_tracker(GameValueScope scope, HasInventory* entity) const {
  switch (scope) {
    case GameValueScope::AGENT: {
      Agent* agent = dynamic_cast<Agent*>(entity);
      if (agent != nullptr) return &agent->stats;
      return nullptr;
    }
    case GameValueScope::COLLECTIVE: {
      GridObject* grid_obj = dynamic_cast<GridObject*>(entity);
      if (grid_obj != nullptr) {
        Collective* coll = grid_obj->getCollective();
        if (coll != nullptr) return &coll->stats;
      }
      return nullptr;
    }
    case GameValueScope::GAME:
      return game_stats;
  }
  return nullptr;
}

}  // namespace mettagrid
