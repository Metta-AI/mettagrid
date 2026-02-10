#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_SYSTEMS_REWARD_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_SYSTEMS_REWARD_HPP_

#include <algorithm>
#include <string>
#include <vector>

#include "core/resolved_game_value.hpp"
#include "core/tag_index.hpp"
#include "core/types.hpp"
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
  };

  std::vector<ResolvedEntry> _resolved_entries;
  float _current_reward = 0.0f;

  // Initialize resolved entries from config.entries
  void init_entries(StatsTracker* agent_stats_tracker,
                    StatsTracker* game_stats_tracker,
                    StatsTracker* collective_stats_tracker,
                    mettagrid::TagIndex* tag_index,
                    const std::vector<std::string>* resource_names) {
    _resolved_entries.clear();
    for (const auto& entry : config.entries) {
      ResolvedEntry re;
      re.numerator = resolve_game_value(entry.numerator,
                                        agent_stats_tracker,
                                        game_stats_tracker,
                                        collective_stats_tracker,
                                        tag_index,
                                        resource_names);
      for (const auto& denom : entry.denominators) {
        re.denominators.push_back(resolve_game_value(
            denom, agent_stats_tracker, game_stats_tracker, collective_stats_tracker, tag_index, resource_names));
      }
      re.weight = entry.weight;
      re.max_value = entry.max_value;
      re.has_max = entry.has_max;
      _resolved_entries.push_back(std::move(re));
    }
  }

  // Compute rewards using resolved entries
  RewardType compute_entries() {
    if (_resolved_entries.empty()) return 0;

    float new_reward = 0.0f;
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

      new_reward += val;
    }

    float delta = new_reward - _current_reward;
    if (delta != 0.0f && reward_ptr != nullptr) {
      *reward_ptr += delta;
      _current_reward = new_reward;
    }
    return delta;
  }

private:
  ResolvedGameValue resolve_game_value(const GameValueConfig& gvc,
                                       StatsTracker* agent_stats,
                                       StatsTracker* game_stats,
                                       StatsTracker* collective_stats,
                                       mettagrid::TagIndex* tag_index,
                                       const std::vector<std::string>* resource_names) {
    ResolvedGameValue rgv;
    rgv.delta = gvc.delta;

    if (gvc.type == GameValueType::TAG_COUNT) {
      rgv.mutable_ = false;
      if (tag_index) {
        rgv.value_ptr = tag_index->get_count_ptr(gvc.id);
      }
      return rgv;
    }

    StatsTracker* tracker = nullptr;
    switch (gvc.scope) {
      case GameValueScope::AGENT:
        tracker = agent_stats;
        break;
      case GameValueScope::COLLECTIVE:
        tracker = collective_stats;
        break;
      case GameValueScope::GAME:
        tracker = game_stats;
        break;
    }

    if (tracker == nullptr) return rgv;

    if (gvc.type == GameValueType::INVENTORY && resource_names != nullptr && gvc.id < resource_names->size()) {
      std::string stat_name = (*resource_names)[gvc.id] + ".amount";
      uint16_t sid = tracker->get_or_create_id(stat_name);
      rgv.value_ptr = tracker->get_ptr(sid);
    } else if (gvc.type == GameValueType::STAT) {
      if (!gvc.stat_name.empty()) {
        uint16_t sid = tracker->get_or_create_id(gvc.stat_name);
        rgv.value_ptr = tracker->get_ptr(sid);
      } else {
        rgv.value_ptr = tracker->get_ptr(gvc.id);
      }
    }

    return rgv;
  }
};

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_SYSTEMS_REWARD_HPP_
