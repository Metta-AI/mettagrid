#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_SYSTEMS_REWARD_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_SYSTEMS_REWARD_HPP_

#include <algorithm>
#include <string>
#include <unordered_map>

#include "core/tag_index.hpp"
#include "core/types.hpp"
#include "objects/collective.hpp"
#include "objects/reward_config.hpp"
#include "systems/stats_tracker.hpp"

// Computes rewards based on stats and configuration
class RewardComputer {
public:
  RewardConfig config;
  RewardType current_stat_reward;
  RewardType* reward_ptr;

  RewardComputer() : current_stat_reward(0), reward_ptr(nullptr) {}

  explicit RewardComputer(const RewardConfig& cfg) : config(cfg), current_stat_reward(0), reward_ptr(nullptr) {}

  void init(RewardType* reward) {
    this->reward_ptr = reward;
  }

  // Compute stat-based rewards
  // Returns the delta applied to reward_ptr
  RewardType compute(StatsTracker* agent_stats,
                     StatsTracker* game_stats_tracker,
                     mettagrid::TagIndex* tag_index,
                     Collective* collective) {
    if (config.empty()) {
      return 0;
    }

    // Prefix for tag-count based rewards (e.g., "tagcount:5" means count of objects with tag_id 5)
    static const std::string tagcount_prefix = "tagcount:";

    float new_stat_reward = 0;

    for (const auto& [stat_name, reward_per_unit] : config.stat_rewards) {
      float stat_value = 0.0f;

      // Check if this is a tag-count based stat (format: "tagcount:{tag_id}")
      if (stat_name.rfind(tagcount_prefix, 0) == 0) {
        // Extract tag_id from stat_name
        if (tag_index != nullptr) {
          try {
            int tag_id = std::stoi(stat_name.substr(tagcount_prefix.length()));
            stat_value = static_cast<float>(tag_index->count_objects_with_tag(tag_id));
          } catch (const std::exception&) {
            // Invalid tag_id format, treat as 0
            stat_value = 0.0f;
          }
        }
      } else {
        // Regular stat lookup from agent, global, and collective stats
        if (agent_stats) {
          stat_value = agent_stats->get(stat_name);
        }
        if (game_stats_tracker) {
          stat_value += game_stats_tracker->get(stat_name);
        }
        if (collective) {
          stat_value += collective->stats.get(stat_name);
        }
      }

      float stats_reward = stat_value * reward_per_unit;

      // Apply tag-based denominator normalization if configured
      auto denom_it = config.stat_reward_denoms.find(stat_name);
      if (denom_it != config.stat_reward_denoms.end() && tag_index != nullptr) {
        size_t object_count = tag_index->count_objects_with_tag(denom_it->second);
        if (object_count > 0) {
          stats_reward /= static_cast<float>(object_count);
        }
        // If object_count is 0, we leave stats_reward unchanged (no division by zero)
      }

      // Apply stat-based denominator normalization if configured
      auto stat_denom_it = config.stat_reward_stat_denoms.find(stat_name);
      if (stat_denom_it != config.stat_reward_stat_denoms.end()) {
        const std::string& denom_stat_name = stat_denom_it->second;
        float denom_value = 0.0f;
        if (agent_stats) {
          denom_value = agent_stats->get(denom_stat_name);
        }
        if (game_stats_tracker) {
          denom_value += game_stats_tracker->get(denom_stat_name);
        }
        if (collective) {
          denom_value += collective->stats.get(denom_stat_name);
        }
        if (denom_value > 0) {
          stats_reward /= denom_value;
        }
        // If denom_value is 0 or negative, we leave stats_reward unchanged (no division by zero)
      }

      if (config.stat_reward_max.count(stat_name) > 0) {
        stats_reward = std::min(stats_reward, config.stat_reward_max.at(stat_name));
      }

      new_stat_reward += stats_reward;
    }

    // Update the reward with the difference
    float reward_delta = new_stat_reward - this->current_stat_reward;
    if (reward_delta != 0.0f && reward_ptr != nullptr) {
      *reward_ptr += reward_delta;
      this->current_stat_reward = new_stat_reward;
    }

    return reward_delta;
  }
};

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_SYSTEMS_REWARD_HPP_
