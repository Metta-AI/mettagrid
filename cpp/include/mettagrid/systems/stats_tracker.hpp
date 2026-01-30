#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_SYSTEMS_STATS_TRACKER_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_SYSTEMS_STATS_TRACKER_HPP_

#include <algorithm>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

#include "core/types.hpp"

// Forward declaration
class MettaGrid;

using InventoryItem = uint8_t;

// Raw observation value before multi-token encoding
struct ObservationValue {
  ObservationType feature_id;
  uint32_t value;
};

class StatsTracker {
private:
  std::unordered_map<std::string, float> _stats;
  // StatsTracker holds a reference to resource_names to make it easier to track stats for each resource.
  // The environment owns this reference, so it should live as long as we're going to use it.
  const std::vector<std::string>* _resource_names;

  // Observation support
  struct ObsConfig {
    std::string name;
    ObservationType feature_id;
    bool delta;
    float prev_value = 0.0f;  // For delta tracking
  };
  std::vector<ObsConfig> _obs_configs;
  std::vector<ObservationValue> _cached_obs_values;

  // Test class needs access for testing
  friend class StatsTrackerTest;

public:
  explicit StatsTracker(const std::vector<std::string>* resource_names) : _stats(), _resource_names(resource_names) {
    if (resource_names == nullptr) {
      throw std::invalid_argument("resource_names cannot be null");
    }
  }

  const std::string& resource_name(InventoryItem item) const {
    return (*_resource_names)[item];
  }

  void add(const std::string& key, float amount) {
    _stats[key] += amount;
  }

  // Increment by 1 (convenience method)
  void incr(const std::string& key) {
    add(key, 1);
  }

  void set(const std::string& key, float value) {
    _stats[key] = value;
  }

  float get(const std::string& key) const {
    auto it = _stats.find(key);
    if (it == _stats.end()) {
      return 0.0f;
    }
    return it->second;
  }

  // Convert to map for Python API
  const std::unordered_map<std::string, float>& to_dict() const {
    return _stats;
  }

  // Reset all statistics
  void reset() {
    _stats.clear();
  }

  // Register a single stat to observe
  void register_observation(const std::string& name, ObservationType feature_id, bool delta) {
    _obs_configs.push_back({name, feature_id, delta, 0.0f});
  }

  // Precompute observation values for this timestep.
  // Call once per timestep (before any per-agent observation emission)
  // to ensure all agents see the same delta values.
  void precompute_observation_values() {
    _cached_obs_values.clear();
    for (auto& obs : _obs_configs) {
      float current = get(obs.name);
      float emit = obs.delta ? (current - obs.prev_value) : current;
      if (obs.delta) {
        obs.prev_value = current;
      }
      _cached_obs_values.push_back({obs.feature_id, static_cast<uint32_t>(std::max(0.0f, emit))});
    }
  }

  // Get the precomputed observation values (safe to call multiple times per timestep)
  const std::vector<ObservationValue>& observation_values() const {
    return _cached_obs_values;
  }
};

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_SYSTEMS_STATS_TRACKER_HPP_
