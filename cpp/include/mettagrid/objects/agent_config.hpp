// agent_config.hpp
#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_AGENT_CONFIG_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_AGENT_CONFIG_HPP_

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <memory>
#include <string>
#include <unordered_map>
#include <vector>

#include "core/grid_object.hpp"
#include "core/types.hpp"
#include "handler/handler_config.hpp"
#include "objects/inventory_config.hpp"
#include "objects/reward_config.hpp"

struct AgentConfig : public GridObjectConfig {
  AgentConfig(TypeId type_id,
              const std::string& type_name,
              unsigned char group_id,
              const std::string& group_name,
              unsigned char freeze_duration = 0,
              ObservationType initial_vibe = 0,
              const InventoryConfig& inventory_config = InventoryConfig(),
              const RewardConfig& reward_config = RewardConfig(),
              const std::unordered_map<InventoryItem, InventoryQuantity>& initial_inventory = {},
              const std::vector<mettagrid::HandlerConfig>& on_tick = {})
      : GridObjectConfig(type_id, type_name, initial_vibe),
        group_id(group_id),
        group_name(group_name),
        freeze_duration(freeze_duration),
        inventory_config(inventory_config),
        reward_config(reward_config),
        initial_inventory(initial_inventory),
        on_tick(on_tick) {}

  unsigned char group_id;
  std::string group_name;
  short freeze_duration;
  InventoryConfig inventory_config;
  RewardConfig reward_config;
  std::unordered_map<InventoryItem, InventoryQuantity> initial_inventory;
  std::vector<mettagrid::HandlerConfig> on_tick;
};

namespace py = pybind11;

inline void bind_agent_config(py::module& m) {
  py::class_<AgentConfig, GridObjectConfig, std::shared_ptr<AgentConfig>>(m, "AgentConfig")
      .def(py::init<TypeId,
                    const std::string&,
                    unsigned char,
                    const std::string&,
                    unsigned char,
                    ObservationType,
                    const InventoryConfig&,
                    const RewardConfig&,
                    const std::unordered_map<InventoryItem, InventoryQuantity>&,
                    const std::vector<mettagrid::HandlerConfig>&>(),
           py::arg("type_id"),
           py::arg("type_name") = "agent",
           py::arg("group_id"),
           py::arg("group_name"),
           py::arg("freeze_duration") = 0,
           py::arg("initial_vibe") = 0,
           py::arg("inventory_config") = InventoryConfig(),
           py::arg("reward_config") = RewardConfig(),
           py::arg("initial_inventory") = std::unordered_map<InventoryItem, InventoryQuantity>(),
           py::arg("on_tick") = std::vector<mettagrid::HandlerConfig>())
      .def_readwrite("type_id", &AgentConfig::type_id)
      .def_readwrite("type_name", &AgentConfig::type_name)
      .def_readwrite("tag_ids", &AgentConfig::tag_ids)
      .def_readwrite("initial_vibe", &AgentConfig::initial_vibe)
      .def_readwrite("group_name", &AgentConfig::group_name)
      .def_readwrite("group_id", &AgentConfig::group_id)
      .def_readwrite("freeze_duration", &AgentConfig::freeze_duration)
      .def_readwrite("inventory_config", &AgentConfig::inventory_config)
      .def_readwrite("reward_config", &AgentConfig::reward_config)
      .def_readwrite("initial_inventory", &AgentConfig::initial_inventory)
      .def_readwrite("on_tick", &AgentConfig::on_tick);
}

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_AGENT_CONFIG_HPP_
