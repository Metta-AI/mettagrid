#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_VIBE_FILTER_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_VIBE_FILTER_HPP_

#include "core/grid_object.hpp"
#include "handler/filters/filter.hpp"
#include "handler/handler_config.hpp"

namespace mettagrid {

/**
 * VibeFilter: Check if entity has a specific vibe
 */
class VibeFilter : public Filter {
public:
  explicit VibeFilter(const VibeFilterConfig& config) : _config(config) {}

  bool passes(const HandlerContext& ctx) const override {
    // Cast to GridObject to access vibe (GridObject inherits from HasVibe)
    GridObject* grid_obj = dynamic_cast<GridObject*>(ctx.resolve(_config.entity));
    if (grid_obj == nullptr) {
      return false;
    }

    return grid_obj->vibe == _config.vibe_id;
  }

private:
  VibeFilterConfig _config;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_VIBE_FILTER_HPP_
