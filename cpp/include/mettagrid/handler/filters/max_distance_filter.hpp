#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_MAX_DISTANCE_FILTER_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_MAX_DISTANCE_FILTER_HPP_

#include <cassert>
#include <cstdlib>
#include <memory>

#include "core/grid_object.hpp"
#include "core/query_system.hpp"
#include "handler/filters/filter.hpp"
#include "handler/handler_config.hpp"

namespace mettagrid {

/**
 * MaxDistanceFilter: Check if entity is within Chebyshev distance of any
 * object returned by a source query.
 *
 * Evaluates the source query via QuerySystem to get candidate objects,
 * then checks if the resolved entity is within Chebyshev distance.
 */
class MaxDistanceFilter : public Filter {
public:
  explicit MaxDistanceFilter(const MaxDistanceFilterConfig& config) : _config(config) {}

  bool passes(const HandlerContext& ctx) const override {
    GridObject* entity = dynamic_cast<GridObject*>(ctx.resolve(_config.entity));
    if (entity == nullptr) {
      return false;
    }

    if (!_config.source) return true;

    auto source_objects = _config.source->evaluate(ctx);

    // radius=0 means unlimited (always matches if source exists)
    if (_config.radius == 0) {
      return !source_objects.empty();
    }

    for (auto* src : source_objects) {
      int dr = std::abs(static_cast<int>(entity->location.r) - static_cast<int>(src->location.r));
      int dc = std::abs(static_cast<int>(entity->location.c) - static_cast<int>(src->location.c));
      if (std::max(dr, dc) <= static_cast<int>(_config.radius)) {
        return true;
      }
    }
    return false;
  }

private:
  MaxDistanceFilterConfig _config;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_MAX_DISTANCE_FILTER_HPP_
