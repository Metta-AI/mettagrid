#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_EVENT_BINDINGS_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_EVENT_BINDINGS_HPP_

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "handler/handler_config.hpp"

namespace py = pybind11;

inline void bind_event_config(py::module& m) {
  using namespace mettagrid;

  // EventConfig for timestep-triggered events
  py::class_<EventConfig, std::shared_ptr<EventConfig>>(m, "EventConfig")
      .def(py::init<>())
      .def(py::init<const std::string&>(), py::arg("name"))
      .def_readwrite("name", &EventConfig::name)
      .def_readwrite("target_tag_id", &EventConfig::target_tag_id)
      .def_readwrite("timesteps", &EventConfig::timesteps)
      .def_readwrite("max_targets", &EventConfig::max_targets)
      .def_readwrite("fallback", &EventConfig::fallback)
      // Add filter methods - each type wraps into the variant
      .def(
          "add_vibe_filter",
          [](EventConfig& self, const VibeFilterConfig& cfg) { self.filters.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_resource_filter",
          [](EventConfig& self, const ResourceFilterConfig& cfg) { self.filters.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_alignment_filter",
          [](EventConfig& self, const AlignmentFilterConfig& cfg) { self.filters.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_tag_filter",
          [](EventConfig& self, const TagFilterConfig& cfg) { self.filters.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_near_filter",
          [](EventConfig& self, const NearFilterConfig& cfg) { self.filters.push_back(cfg); },
          py::arg("filter"))
      // Add mutation methods - each type wraps into the variant
      .def(
          "add_resource_delta_mutation",
          [](EventConfig& self, const ResourceDeltaMutationConfig& cfg) { self.mutations.push_back(cfg); },
          py::arg("mutation"))
      .def(
          "add_resource_transfer_mutation",
          [](EventConfig& self, const ResourceTransferMutationConfig& cfg) { self.mutations.push_back(cfg); },
          py::arg("mutation"))
      .def(
          "add_alignment_mutation",
          [](EventConfig& self, const AlignmentMutationConfig& cfg) { self.mutations.push_back(cfg); },
          py::arg("mutation"))
      .def(
          "add_freeze_mutation",
          [](EventConfig& self, const FreezeMutationConfig& cfg) { self.mutations.push_back(cfg); },
          py::arg("mutation"))
      .def(
          "add_clear_inventory_mutation",
          [](EventConfig& self, const ClearInventoryMutationConfig& cfg) { self.mutations.push_back(cfg); },
          py::arg("mutation"))
      .def(
          "add_attack_mutation",
          [](EventConfig& self, const AttackMutationConfig& cfg) { self.mutations.push_back(cfg); },
          py::arg("mutation"))
      .def(
          "add_stats_mutation",
          [](EventConfig& self, const StatsMutationConfig& cfg) { self.mutations.push_back(cfg); },
          py::arg("mutation"))
      .def(
          "add_add_tag_mutation",
          [](EventConfig& self, const AddTagMutationConfig& cfg) { self.mutations.push_back(cfg); },
          py::arg("mutation"))
      .def(
          "add_remove_tag_mutation",
          [](EventConfig& self, const RemoveTagMutationConfig& cfg) { self.mutations.push_back(cfg); },
          py::arg("mutation"));
}

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_EVENT_BINDINGS_HPP_
