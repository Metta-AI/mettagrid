#include <pybind11/pybind11.h>

#include "bindings/mettagrid_c.hpp"
#include "profiling.hpp"

namespace py = pybind11;

void bind_profiling_properties(py::class_<MettaGrid>& cls) {
  py::class_<StepTimingStats>(cls, "StepTimingStats")
      .def_readonly("reset_ns", &StepTimingStats::reset_ns)
      .def_readonly("events_ns", &StepTimingStats::events_ns)
      .def_readonly("actions_ns", &StepTimingStats::actions_ns)
      .def_readonly("on_tick_ns", &StepTimingStats::on_tick_ns)
      .def_readonly("aoe_ns", &StepTimingStats::aoe_ns)
      .def_readonly("collectives_ns", &StepTimingStats::collectives_ns)
      .def_readonly("observations_ns", &StepTimingStats::observations_ns)
      .def_readonly("rewards_ns", &StepTimingStats::rewards_ns)
      .def_readonly("truncation_ns", &StepTimingStats::truncation_ns)
      .def_readonly("total_ns", &StepTimingStats::total_ns);

  py::class_<MettaGrid::ObsValidationStats>(cls, "ObsValidationStats")
      .def_readonly("comparison_count", &MettaGrid::ObsValidationStats::comparison_count)
      .def_readonly("mismatch_count", &MettaGrid::ObsValidationStats::mismatch_count)
      .def_readonly("original_time_ns", &MettaGrid::ObsValidationStats::original_time_ns)
      .def_readonly("optimized_time_ns", &MettaGrid::ObsValidationStats::optimized_time_ns);

  cls.def_property_readonly("last_obs_time_ns", &MettaGrid::last_obs_time_ns)
      .def_property_readonly("step_timing", &MettaGrid::step_timing, py::return_value_policy::reference_internal)
      .def_property_readonly(
          "obs_validation_stats", &MettaGrid::obs_validation_stats, py::return_value_policy::reference_internal);
}
