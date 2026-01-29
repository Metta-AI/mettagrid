// reward_config.hpp
#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_REWARD_CONFIG_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_REWARD_CONFIG_HPP_

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <string>
#include <unordered_map>

#include "core/types.hpp"

// Configuration for stat-based reward computation
struct RewardConfig {
  // Reward per unit for each stat
  std::unordered_map<std::string, RewardType> stat_rewards;
  // Maximum reward cap per stat
  std::unordered_map<std::string, RewardType> stat_reward_max;
  // Denominator tag IDs for reward normalization: stat_name -> tag_id
  // When set, the reward is divided by the count of objects with that tag
  std::unordered_map<std::string, int> stat_reward_denoms;
  // Denominator stat names for stat-based reward normalization: stat_name -> denom_stat_name
  // When set, the reward is divided by the value of the denominator stat
  std::unordered_map<std::string, std::string> stat_reward_stat_denoms;

  RewardConfig() = default;

  RewardConfig(const std::unordered_map<std::string, RewardType>& stat_rewards,
               const std::unordered_map<std::string, RewardType>& stat_reward_max = {},
               const std::unordered_map<std::string, int>& stat_reward_denoms = {},
               const std::unordered_map<std::string, std::string>& stat_reward_stat_denoms = {})
      : stat_rewards(stat_rewards),
        stat_reward_max(stat_reward_max),
        stat_reward_denoms(stat_reward_denoms),
        stat_reward_stat_denoms(stat_reward_stat_denoms) {}

  bool empty() const {
    return stat_rewards.empty();
  }
};

namespace py = pybind11;

inline void bind_reward_config(py::module& m) {
  py::class_<RewardConfig>(m, "RewardConfig")
      .def(py::init<>())
      .def(py::init<const std::unordered_map<std::string, RewardType>&,
                    const std::unordered_map<std::string, RewardType>&,
                    const std::unordered_map<std::string, int>&,
                    const std::unordered_map<std::string, std::string>&>(),
           py::arg("stat_rewards"),
           py::arg("stat_reward_max") = std::unordered_map<std::string, RewardType>(),
           py::arg("stat_reward_denoms") = std::unordered_map<std::string, int>(),
           py::arg("stat_reward_stat_denoms") = std::unordered_map<std::string, std::string>())
      .def_readwrite("stat_rewards", &RewardConfig::stat_rewards)
      .def_readwrite("stat_reward_max", &RewardConfig::stat_reward_max)
      .def_readwrite("stat_reward_denoms", &RewardConfig::stat_reward_denoms)
      .def_readwrite("stat_reward_stat_denoms", &RewardConfig::stat_reward_stat_denoms);
}

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_REWARD_CONFIG_HPP_
