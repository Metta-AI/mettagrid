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
 * MaxDistanceFilter: Chebyshev distance check.
 *
 * radius=0 means unlimited (always passes, no distance constraint).
 *
 * Two modes:
 * - Unary (source query set): entity is within radius of any query result.
 *   With radius=0, passes if source query returns any results (distance unchecked).
 * - Binary (source=nullptr): Chebyshev distance(actor, entity) <= radius,
 *   or unconditionally when radius=0.
 *   Used in ClosureQuery edge_filters where actor=net_member, entity=candidate.
 */
class MaxDistanceFilter : public Filter {
public:
  explicit MaxDistanceFilter(const MaxDistanceFilterConfig& config) : _config(config) {}

  bool passes(const HandlerContext& ctx) const override {
    GridObject* entity = dynamic_cast<GridObject*>(ctx.resolve(_config.entity));
    if (entity == nullptr) {
      return false;
    }

    if (!_config.source) {
      // Binary mode: check distance from actor to entity
      if (ctx.actor == nullptr) return false;
      if (_config.radius == 0) return true;  // 0 = unlimited range
      int dr = std::abs(static_cast<int>(entity->location.r) - static_cast<int>(ctx.actor->location.r));
      int dc = std::abs(static_cast<int>(entity->location.c) - static_cast<int>(ctx.actor->location.c));
      return std::max(dr, dc) <= static_cast<int>(_config.radius);
    }

    auto source_objects = _config.source->evaluate(ctx);

    if (_config.radius == 0) {  // 0 = unlimited range, skip distance check
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
