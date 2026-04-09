#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_PERIODIC_FILTER_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_PERIODIC_FILTER_HPP_

#include "core/filter_config.hpp"
#include "handler/filters/filter.hpp"
#include "handler/handler_context.hpp"

namespace mettagrid {

/**
 * PeriodicFilter: passes every `period` timesteps starting at `start_on`.
 *
 * Passes when: timestep >= start_on && (timestep - start_on) % period == 0
 */
class PeriodicFilter : public Filter {
public:
  explicit PeriodicFilter(const PeriodicFilterConfig& config) : _period(config.period), _start_on(config.start_on) {}

  bool passes(const HandlerContext& ctx) const override {
    if (ctx.timestep < _start_on) {
      return false;
    }
    return (ctx.timestep - _start_on) % _period == 0;
  }

private:
  unsigned int _period;
  unsigned int _start_on;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_PERIODIC_FILTER_HPP_
