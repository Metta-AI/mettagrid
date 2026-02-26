#include "core/game_value.hpp"

#include <type_traits>

#include "core/query_config.hpp"
#include "handler/handler_context.hpp"
#include "objects/has_inventory.hpp"
#include "systems/stats_tracker.hpp"

ResolvedGameValue resolve_game_value(const GameValueConfig& gvc, const mettagrid::HandlerContext& ctx) {
  return std::visit(
      [&](auto&& c) -> ResolvedGameValue {
        using T = std::decay_t<decltype(c)>;
        ResolvedGameValue rgv;

        if constexpr (std::is_same_v<T, InventoryValueConfig>) {
          HasInventory* inventory_entity = ctx.actor;
          if (inventory_entity) {
            rgv.mutable_ = false;
            auto resource_id = c.id;
            rgv.compute_fn = [inventory_entity, resource_id]() -> float {
              return static_cast<float>(inventory_entity->inventory.amount(resource_id));
            };
          } else {
            StatsTracker* tracker = ctx.resolve_stats_tracker(c.scope, ctx.actor);
            if (tracker != nullptr) {
              std::string stat_name = tracker->resource_name(c.id) + ".amount";
              uint16_t sid = tracker->get_or_create_id(stat_name);
              rgv.value_ptr = tracker->get_ptr(sid);
            }
          }
        } else if constexpr (std::is_same_v<T, StatValueConfig>) {
          rgv.delta = c.delta;
          StatsTracker* tracker = ctx.resolve_stats_tracker(c.scope, ctx.actor);
          if (tracker != nullptr) {
            if (!c.stat_name.empty()) {
              uint16_t sid = tracker->get_or_create_id(c.stat_name);
              rgv.value_ptr = tracker->get_ptr(sid);
            } else {
              rgv.value_ptr = tracker->get_ptr(c.id);
            }
          }
        } else if constexpr (std::is_same_v<T, ConstValueConfig>) {
          rgv.mutable_ = false;
          float val = c.value;
          rgv.compute_fn = [val]() -> float { return val; };
        } else if constexpr (std::is_same_v<T, QueryInventoryValueConfig>) {
          rgv.mutable_ = false;
          auto query = c.query;
          auto resource_id = c.id;
          rgv.compute_fn = [query, resource_id, ctx]() -> float {
            if (!query) return 0.0f;
            auto results = query->evaluate(ctx);
            float total = 0.0f;
            for (auto* obj : results) {
              total += static_cast<float>(obj->inventory.amount(resource_id));
            }
            return total;
          };
        } else if constexpr (std::is_same_v<T, QueryCountValueConfig>) {
          rgv.mutable_ = false;
          auto query = c.query;
          rgv.compute_fn = [query, ctx]() -> float {
            if (!query) return 0.0f;
            auto results = query->evaluate(ctx);
            return static_cast<float>(results.size());
          };
        }
        return rgv;
      },
      gvc);
}
