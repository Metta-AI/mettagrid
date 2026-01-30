#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_NEAR_FILTER_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_NEAR_FILTER_HPP_

#include <cassert>
#include <cstdlib>
#include <memory>
#include <vector>

#include "core/grid_object.hpp"
#include "handler/filters/filter.hpp"
#include "handler/handler_config.hpp"

namespace mettagrid {

/**
 * NearFilter: Check if entity is near an object matching inner filters.
 *
 * Passes if target is within radius of an object that passes ALL inner filters.
 * This is useful for proximity-based mechanics.
 *
 * Example usage:
 *   isNear("type:junction", radius=3)  # Near junctions
 *   isNear("type:clips")  # Near clips objects
 */
class NearFilter : public Filter {
public:
  NearFilter(const NearFilterConfig& config, std::vector<std::unique_ptr<Filter>> filters = {})
      : _config(config), _filters(std::move(filters)) {}

  // Get mutable access to filters for collective resolution
  std::vector<std::unique_ptr<Filter>>& filters() {
    return _filters;
  }

  bool passes(const HandlerContext& ctx) const override {
    // NearFilter requires a tag index and valid target_tag
    assert(ctx.tag_index != nullptr && "NearFilter requires tag_index");
    assert(_config.target_tag >= 0 && "NearFilter requires valid target_tag");

    // Get GridObject to check proximity
    GridObject* grid_obj = dynamic_cast<GridObject*>(ctx.resolve(_config.entity));
    if (grid_obj == nullptr) {
      return false;
    }

    // Find objects with the tag and check if any are within radius AND pass filters
    const auto& candidates = ctx.tag_index->get_objects_with_tag(_config.target_tag);
    for (GridObject* candidate : candidates) {
      if (is_within_radius(grid_obj, candidate)) {
        // If no filters, proximity alone is sufficient
        if (_filters.empty()) {
          return true;
        }

        // Create context with candidate as target and check all filters
        // Include collectives from outer context for alignment filter lookups
        HandlerContext inner_ctx(
            ctx.actor, candidate, ctx.game_stats, ctx.tag_index, ctx.collectives, ctx.skip_on_update_trigger);
        bool passes_all_filters = true;
        for (const auto& filter : _filters) {
          if (!filter->passes(inner_ctx)) {
            passes_all_filters = false;
            break;
          }
        }
        if (passes_all_filters) {
          return true;
        }
      }
    }
    return false;
  }

  // Get the radius for this filter
  int radius() const {
    return _config.radius;
  }

private:
  // Check if obj2 is within radius of obj1 (Chebyshev distance)
  bool is_within_radius(GridObject* obj1, GridObject* obj2) const {
    int dr = std::abs(obj1->location.r - obj2->location.r);
    int dc = std::abs(obj1->location.c - obj2->location.c);
    return std::max(dr, dc) <= _config.radius;
  }

  NearFilterConfig _config;
  std::vector<std::unique_ptr<Filter>> _filters;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_NEAR_FILTER_HPP_
