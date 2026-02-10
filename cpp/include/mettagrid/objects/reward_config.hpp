// reward_config.hpp
#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_REWARD_CONFIG_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_REWARD_CONFIG_HPP_

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <cstdint>
#include <limits>
#include <string>
#include <vector>

#include "core/game_value_config.hpp"
#include "core/types.hpp"

// A single reward entry using GameValueConfig references
struct RewardEntry {
  GameValueConfig numerator;
  std::vector<GameValueConfig> denominators;
  float weight = 1.0f;
  float max_value = std::numeric_limits<float>::max();
  bool has_max = false;
  // Reward role gating. 255 means "all roles". Otherwise this is a role id (0..3 for miner/aligner/scrambler/scout)
  // and the reward's weight is scaled by the agent's soft-role weight for that role (`agent:role:*`, 0..255).
  uint8_t role = 255;
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
      .def_readwrite("numerator", &RewardEntry::numerator)
      .def_readwrite("denominators", &RewardEntry::denominators)
      .def_readwrite("weight", &RewardEntry::weight)
      .def_readwrite("max_value", &RewardEntry::max_value)
      .def_readwrite("has_max", &RewardEntry::has_max)
      .def_readwrite("role", &RewardEntry::role);

  py::class_<RewardConfig>(m, "RewardConfig").def(py::init<>()).def_readwrite("entries", &RewardConfig::entries);
}

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_REWARD_CONFIG_HPP_
