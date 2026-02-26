#include "core/game_value.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
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
            auto resource_id = c.id;
            rgv.compute_fn = [inventory_entity, resource_id]() -> float {
              return static_cast<float>(inventory_entity->inventory.amount(resource_id));
            };
            rgv.update_fn = [inventory_entity, resource_id](float delta) {
              inventory_entity->inventory.update(resource_id, static_cast<InventoryDelta>(delta));
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
        } else if constexpr (std::is_same_v<T, std::shared_ptr<SumValueConfig>>) {
          rgv.mutable_ = false;
          if (!c) {
            rgv.compute_fn = []() -> float { return 0.0f; };
            return rgv;
          }
          auto values = c->values;
          auto weights = c->weights;
          bool apply_log = c->log;
          if (!weights.empty() && weights.size() != values.size()) {
            throw std::runtime_error("SumValueConfig.weights size must match values size");
          }
          rgv.compute_fn = [values, weights, apply_log, ctx]() -> float {
            float total = 0.0f;
            for (size_t i = 0; i < values.size(); ++i) {
              float term = ctx.resolve_game_value(values[i], mettagrid::EntityRef::actor);
              if (apply_log) {
                term = std::log(term + 1.0f);
              }
              if (!weights.empty()) {
                term *= weights[i];
              }
              total += term;
            }
            return total;
          };
        } else if constexpr (std::is_same_v<T, std::shared_ptr<RatioValueConfig>>) {
          rgv.mutable_ = false;
          if (!c) {
            rgv.compute_fn = []() -> float { return 0.0f; };
            return rgv;
          }
          auto numerator = c->numerator;
          auto denominator = c->denominator;
          rgv.compute_fn = [numerator, denominator, ctx]() -> float {
            float num = ctx.resolve_game_value(numerator, mettagrid::EntityRef::actor);
            float den = ctx.resolve_game_value(denominator, mettagrid::EntityRef::actor);
            if (den > 0.0f) {
              return num / den;
            }
            return num;
          };
        } else if constexpr (std::is_same_v<T, std::shared_ptr<MaxValueConfig>>) {
          rgv.mutable_ = false;
          if (!c || c->values.empty()) {
            rgv.compute_fn = []() -> float { return 0.0f; };
            return rgv;
          }
          auto values = c->values;
          rgv.compute_fn = [values, ctx]() -> float {
            float best = std::numeric_limits<float>::lowest();
            for (const auto& value : values) {
              best = std::max(best, ctx.resolve_game_value(value, mettagrid::EntityRef::actor));
            }
            return best;
          };
        } else if constexpr (std::is_same_v<T, std::shared_ptr<MinValueConfig>>) {
          rgv.mutable_ = false;
          if (!c || c->values.empty()) {
            rgv.compute_fn = []() -> float { return 0.0f; };
            return rgv;
          }
          auto values = c->values;
          rgv.compute_fn = [values, ctx]() -> float {
            float best = std::numeric_limits<float>::max();
            for (const auto& value : values) {
              best = std::min(best, ctx.resolve_game_value(value, mettagrid::EntityRef::actor));
            }
            return best;
          };
        }
        return rgv;
      },
      gvc);
}
