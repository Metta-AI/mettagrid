#include "handler/handler_context.hpp"

#include <type_traits>

#include "core/query_system.hpp"
#include "objects/agent.hpp"

namespace mettagrid {

float HandlerContext::resolve_game_value(const GameValueConfig& cfg, EntityRef entity_ref) const {
  return std::visit(
      [&](auto&& c) -> float {
        using T = std::decay_t<decltype(c)>;
        if constexpr (std::is_same_v<T, InventoryValueConfig>) {
          EntityRef ref = entity_ref;
          if (c.scope == GameValueScope::COLLECTIVE) {
            if (ref == EntityRef::actor)
              ref = EntityRef::actor_collective;
            else if (ref == EntityRef::target)
              ref = EntityRef::target_collective;
          }
          HasInventory* entity = resolve(ref);
          if (!entity) return 0.0f;
          return static_cast<float>(entity->inventory.amount(c.id));
        } else if constexpr (std::is_same_v<T, StatValueConfig>) {
          HasInventory* entity = resolve(entity_ref);
          StatsTracker* tracker = resolve_stats_tracker(c.scope, entity);
          if (!tracker) return 0.0f;
          if (!c.stat_name.empty()) return tracker->get(c.stat_name);
          return *tracker->get_ptr(c.id);
        } else if constexpr (std::is_same_v<T, TagCountValueConfig>) {
          if (!tag_index) return 0.0f;
          return static_cast<float>(tag_index->count_objects_with_tag(c.id));
        } else if constexpr (std::is_same_v<T, ConstValueConfig>) {
          return c.value;
        } else if constexpr (std::is_same_v<T, QueryInventoryValueConfig>) {
          if (!c.query || !query_system) return 0.0f;
          auto results = c.query->evaluate(*query_system);
          float total = 0.0f;
          for (auto* obj : results) {
            total += static_cast<float>(obj->inventory.amount(c.id));
          }
          return total;
        }
        return 0.0f;
      },
      cfg);
}

StatsTracker* HandlerContext::resolve_stats_tracker(GameValueScope scope, HasInventory* entity) const {
  switch (scope) {
    case GameValueScope::AGENT: {
      Agent* agent = dynamic_cast<Agent*>(entity);
      if (agent != nullptr) return &agent->stats;
      return nullptr;
    }
    case GameValueScope::COLLECTIVE: {
      Collective* coll = get_collective(entity);
      if (coll != nullptr) return &coll->stats;
      return nullptr;
    }
    case GameValueScope::GAME:
      return game_stats;
  }
  return nullptr;
}

}  // namespace mettagrid
