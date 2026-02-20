#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_SYSTEMS_REWARD_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_SYSTEMS_REWARD_HPP_

#include <algorithm>
#include <functional>
#include <string>
#include <type_traits>
#include <vector>

#include "core/query_config.hpp"
#include "core/resolved_game_value.hpp"
#include "core/tag_index.hpp"
#include "core/types.hpp"
#include "handler/handler_context.hpp"
#include "objects/reward_config.hpp"
#include "systems/stats_tracker.hpp"

// Computes rewards based on stats and configuration
class RewardHelper {
public:
  RewardConfig config;
  RewardType* reward_ptr;

  RewardHelper() : reward_ptr(nullptr) {}

  explicit RewardHelper(const RewardConfig& cfg) : config(cfg), reward_ptr(nullptr) {}

  void init(RewardType* reward) {
    this->reward_ptr = reward;
  }

  struct ResolvedEntry {
    ResolvedGameValue numerator;
    std::vector<ResolvedGameValue> denominators;
    float weight = 1.0f;
    float max_value = 0.0f;
    bool has_max = false;
    bool accumulate = false;
    float prev_value = 0.0f;
  };

  std::vector<ResolvedEntry> _resolved_entries;

  float current_reward() const {
    float total = 0.0f;
    for (const auto& entry : _resolved_entries) {
      total += entry.prev_value;
    }
    return total;
  }

  // Initialize resolved entries from config.entries
  void init_entries(StatsTracker* agent_stats_tracker,
                    StatsTracker* collective_stats_tracker,
                    const mettagrid::HandlerContext* game_ctx,
                    const std::vector<std::string>* resource_names) {
    _resolved_entries.clear();
    for (const auto& entry : config.entries) {
      ResolvedEntry re;
      re.numerator =
          resolve_game_value(entry.numerator, agent_stats_tracker, collective_stats_tracker, game_ctx, resource_names);
      for (const auto& denom : entry.denominators) {
        re.denominators.push_back(
            resolve_game_value(denom, agent_stats_tracker, collective_stats_tracker, game_ctx, resource_names));
      }
      re.weight = entry.weight;
      re.max_value = entry.max_value;
      re.has_max = entry.has_max;
      re.accumulate = entry.accumulate;
      _resolved_entries.push_back(std::move(re));
    }
  }

  // Compute rewards using resolved entries
  RewardType compute_entries() {
    if (_resolved_entries.empty()) return 0;

    float total_delta = 0.0f;
    for (auto& entry : _resolved_entries) {
      float val = entry.numerator.read() * entry.weight;

      for (auto& denom : entry.denominators) {
        float d = denom.read();
        if (d > 0.0f) {
          val /= d;
        }
      }

      if (entry.has_max) {
        val = std::min(val, entry.max_value);
      }

      if (entry.accumulate) {
        total_delta += val;
      } else {
        total_delta += val - entry.prev_value;
      }
      entry.prev_value = val;
    }

    if (total_delta != 0.0f && reward_ptr != nullptr) {
      *reward_ptr += total_delta;
    }
    return total_delta;
  }

private:
  StatsTracker* resolve_tracker(GameValueScope scope,
                                StatsTracker* agent_stats,
                                StatsTracker* collective_stats,
                                StatsTracker* game_stats) {
    switch (scope) {
      case GameValueScope::AGENT:
        return agent_stats;
      case GameValueScope::COLLECTIVE:
        return collective_stats;
      case GameValueScope::GAME:
        return game_stats;
    }
    return nullptr;
  }

  ResolvedGameValue resolve_game_value(const GameValueConfig& gvc,
                                       StatsTracker* agent_stats,
                                       StatsTracker* collective_stats,
                                       const mettagrid::HandlerContext* game_ctx,
                                       const std::vector<std::string>* resource_names) {
    return std::visit(
        [&](auto&& c) -> ResolvedGameValue {
          using T = std::decay_t<decltype(c)>;
          ResolvedGameValue rgv;

          if constexpr (std::is_same_v<T, TagCountValueConfig>) {
            rgv.mutable_ = false;
            if (game_ctx && game_ctx->tag_index) {
              rgv.value_ptr = game_ctx->tag_index->get_count_ptr(c.id);
            }
          } else if constexpr (std::is_same_v<T, QueryInventoryValueConfig>) {
            rgv.mutable_ = false;
            auto query = c.query;
            auto resource_id = c.id;
            rgv.compute_fn = [query, resource_id, game_ctx]() -> float {
              if (!query || !game_ctx) return 0.0f;
              auto results = query->evaluate(*game_ctx);
              float total = 0.0f;
              for (auto* obj : results) {
                total += static_cast<float>(obj->inventory.amount(resource_id));
              }
              return total;
            };
          } else if constexpr (std::is_same_v<T, ConstValueConfig>) {
            rgv.mutable_ = false;
            float val = c.value;
            rgv.compute_fn = [val]() -> float { return val; };
          } else if constexpr (std::is_same_v<T, InventoryValueConfig>) {
            StatsTracker* tracker =
                resolve_tracker(c.scope, agent_stats, collective_stats, game_ctx ? game_ctx->game_stats : nullptr);
            if (tracker != nullptr && resource_names != nullptr && c.id < resource_names->size()) {
              std::string stat_name = (*resource_names)[c.id] + ".amount";
              uint16_t sid = tracker->get_or_create_id(stat_name);
              rgv.value_ptr = tracker->get_ptr(sid);
            }
          } else if constexpr (std::is_same_v<T, StatValueConfig>) {
            rgv.delta = c.delta;
            StatsTracker* tracker =
                resolve_tracker(c.scope, agent_stats, collective_stats, game_ctx ? game_ctx->game_stats : nullptr);
            if (tracker != nullptr) {
              if (!c.stat_name.empty()) {
                uint16_t sid = tracker->get_or_create_id(c.stat_name);
                rgv.value_ptr = tracker->get_ptr(sid);
              } else {
                rgv.value_ptr = tracker->get_ptr(c.id);
              }
            }
          }
          return rgv;
        },
        gvc);
  }
};

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_SYSTEMS_REWARD_HPP_
