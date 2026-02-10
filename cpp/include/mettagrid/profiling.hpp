#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_PROFILING_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_PROFILING_HPP_

// Per-phase timing breakdown of _step() (nanoseconds).
// C++ internal timing only — Python/pybind11 overhead is not included.
struct StepTimingStats {
  double reset_ns = 0;
  double events_ns = 0;
  double actions_ns = 0;
  double on_tick_ns = 0;
  double aoe_ns = 0;
  double collectives_ns = 0;
  double observations_ns = 0;
  double rewards_ns = 0;
  double truncation_ns = 0;
  double total_ns = 0;
};

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_PROFILING_HPP_
