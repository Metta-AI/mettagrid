#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_SYSTEMS_REWARD_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_SYSTEMS_REWARD_HPP_

#include <string>
#include <vector>

#include "core/game_value.hpp"
#include "core/resolved_game_value.hpp"
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
    ResolvedGameValue reward;
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
  void init_entries(const mettagrid::HandlerContext& ctx) {
    _resolved_entries.clear();
    for (const auto& entry : config.entries) {
      ResolvedEntry re;
      re.reward = resolve_game_value(entry.reward, ctx);
      re.accumulate = entry.accumulate;
      _resolved_entries.push_back(std::move(re));
    }
  }

  // Compute rewards using resolved entries
  RewardType compute_entries() {
    if (_resolved_entries.empty()) {
      return 0;
    }

    float total_delta = 0.0f;
    for (auto& entry : _resolved_entries) {
      float val = entry.reward.read();

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
};

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_SYSTEMS_REWARD_HPP_
