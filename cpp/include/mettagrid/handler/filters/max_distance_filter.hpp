#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_MAX_DISTANCE_FILTER_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_MAX_DISTANCE_FILTER_HPP_

#include <cassert>
#include <cstdint>
#include <memory>

#include "core/grid_object.hpp"
#include "core/query_system.hpp"
#include "handler/filters/filter.hpp"
#include "handler/handler_config.hpp"

namespace mettagrid {

/**
 * MaxDistanceFilter: L2 distance check (sum of squares, no sqrt).
 *
 * radius=0 means unlimited (always passes, no distance constraint).
 *
 * Two modes:
 * - Unary (source query set): entity is within radius of any query result.
 *   With radius=0, passes if source query returns any results (distance unchecked).
 * - Binary (source=nullptr): L2 distance(actor, entity) <= radius,
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
      if (_config.radius == 0) return true;
      int64_t dr = static_cast<int64_t>(entity->location.r) - static_cast<int64_t>(ctx.actor->location.r);
      int64_t dc = static_cast<int64_t>(entity->location.c) - static_cast<int64_t>(ctx.actor->location.c);
      int64_t r = static_cast<int64_t>(_config.radius);
      return dr * dr + dc * dc <= r * r;
    }

    auto source_objects = _config.source->evaluate(ctx);

    if (_config.radius == 0) {  // 0 = unlimited range, skip distance check
      return !source_objects.empty();
    }

    int64_t r = static_cast<int64_t>(_config.radius);
    int64_t r2 = r * r;
    for (auto* src : source_objects) {
      int64_t dr = static_cast<int64_t>(entity->location.r) - static_cast<int64_t>(src->location.r);
      int64_t dc = static_cast<int64_t>(entity->location.c) - static_cast<int64_t>(src->location.c);
      if (dr * dr + dc * dc <= r2) {
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
