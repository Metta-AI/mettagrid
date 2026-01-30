#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_INVENTORY_CONFIG_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_INVENTORY_CONFIG_HPP_

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <string>
#include <unordered_map>
#include <vector>

#include "core/types.hpp"
#include "objects/constants.hpp"

// Limit definition: resources that share the limit, min/max limit values, and modifiers
// Modifiers map: item_id -> bonus_per_item (e.g., gear -> 1 means each gear adds 1 to limit)
// Effective limit = clamp(sum(modifier_bonus * quantity_held), min_limit, max_limit)
struct LimitDef {
  std::vector<InventoryItem> resources;
  InventoryQuantity min_limit;
  InventoryQuantity max_limit;
  std::unordered_map<InventoryItem, InventoryQuantity> modifiers;

  LimitDef() : min_limit(0), max_limit(65535) {}
  LimitDef(const std::vector<InventoryItem>& resources,
           InventoryQuantity min_limit,
           InventoryQuantity max_limit = 65535,
           const std::unordered_map<InventoryItem, InventoryQuantity>& modifiers = {})
      : resources(resources), min_limit(min_limit), max_limit(max_limit), modifiers(modifiers) {}
};

struct InventoryConfig {
  std::vector<LimitDef> limit_defs;

  InventoryConfig() = default;
};

namespace py = pybind11;

inline void bind_inventory_config(py::module& m) {
  py::class_<LimitDef>(m, "LimitDef")
      .def(py::init<>())
      .def(py::init<const std::vector<InventoryItem>&,
                    InventoryQuantity,
                    InventoryQuantity,
                    const std::unordered_map<InventoryItem, InventoryQuantity>&>(),
           py::arg("resources"),
           py::arg("min_limit"),
           py::arg("max_limit") = 65535,
           py::arg("modifiers") = std::unordered_map<InventoryItem, InventoryQuantity>())
      .def_readwrite("resources", &LimitDef::resources)
      .def_readwrite("min_limit", &LimitDef::min_limit)
      .def_readwrite("max_limit", &LimitDef::max_limit)
      .def_readwrite("modifiers", &LimitDef::modifiers);

  py::class_<InventoryConfig>(m, "InventoryConfig")
      .def(py::init<>())
      .def_readwrite("limit_defs", &InventoryConfig::limit_defs);
}
#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_INVENTORY_CONFIG_HPP_
