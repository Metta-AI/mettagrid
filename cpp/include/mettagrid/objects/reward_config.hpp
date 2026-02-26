// reward_config.hpp
#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_REWARD_CONFIG_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_REWARD_CONFIG_HPP_

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <vector>

#include "core/game_value_config.hpp"
#include "core/types.hpp"

struct RewardEntry {
  GameValueConfig reward = ConstValueConfig{};
  bool accumulate = false;  // Add value each step instead of tracking delta
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
  py::class_<RewardEntry>(m, "RewardEntry")
      .def(py::init<>())
      .def_readwrite("reward", &RewardEntry::reward)
      .def_readwrite("accumulate", &RewardEntry::accumulate);

  py::class_<RewardConfig>(m, "RewardConfig").def(py::init<>()).def_readwrite("entries", &RewardConfig::entries);
}

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_REWARD_CONFIG_HPP_
