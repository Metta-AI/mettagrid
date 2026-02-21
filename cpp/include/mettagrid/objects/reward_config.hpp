// reward_config.hpp
#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_REWARD_CONFIG_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_REWARD_CONFIG_HPP_

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <limits>
#include <string>
#include <vector>

#include "core/game_value_config.hpp"
#include "core/types.hpp"

enum class AggregationMode : uint8_t {
  SUM,       // sum of all numerators (default)
  SUM_LOGS,  // sum(log(val + 1)) across all numerators
};

// A single reward entry using GameValueConfig references
struct RewardEntry {
  std::vector<GameValueConfig> numerators;
  std::vector<GameValueConfig> denominators;
  float weight = 1.0f;
  float max_value = std::numeric_limits<float>::max();
  bool has_max = false;
  bool accumulate = false;  // Add value each step instead of tracking delta
  AggregationMode aggregation_mode = AggregationMode::SUM;
};

// Configuration for reward computation using GameValueConfig entries
struct RewardConfig {
  std::vector<RewardEntry> entries;

  RewardConfig() = default;

  bool empty() const {
    return entries.empty();
  }
};

namespace py = pybind11;

inline void bind_reward_config(py::module& m) {
  py::enum_<AggregationMode>(m, "AggregationMode")
      .value("SUM", AggregationMode::SUM)
      .value("SUM_LOGS", AggregationMode::SUM_LOGS);

  py::class_<RewardEntry>(m, "RewardEntry")
      .def(py::init<>())
      .def_readwrite("numerators", &RewardEntry::numerators)
      .def_readwrite("denominators", &RewardEntry::denominators)
      .def_readwrite("weight", &RewardEntry::weight)
      .def_readwrite("max_value", &RewardEntry::max_value)
      .def_readwrite("has_max", &RewardEntry::has_max)
      .def_readwrite("accumulate", &RewardEntry::accumulate)
      .def_readwrite("aggregation_mode", &RewardEntry::aggregation_mode);

  py::class_<RewardConfig>(m, "RewardConfig").def(py::init<>()).def_readwrite("entries", &RewardConfig::entries);
}

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_REWARD_CONFIG_HPP_
