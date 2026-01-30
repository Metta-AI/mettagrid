#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_TAG_FILTER_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_TAG_FILTER_HPP_

#include "core/grid_object.hpp"
#include "handler/filters/filter.hpp"
#include "handler/handler_config.hpp"

namespace mettagrid {

/**
 * TagFilter: Check if entity has a specific tag
 *
 * Used by handlers and events to filter by tag.
 * Tags are specified in "name:value" format in config (e.g., "type:hub").
 */
class TagFilter : public Filter {
public:
  explicit TagFilter(const TagFilterConfig& config) : _config(config) {}

  bool passes(const HandlerContext& ctx) const override {
    // Get GridObject to access tag_ids
    GridObject* grid_obj = dynamic_cast<GridObject*>(ctx.resolve(_config.entity));
    if (grid_obj == nullptr) {
      return false;
    }

    // Check if entity has the required tag
    for (int entity_tag : grid_obj->tag_ids) {
      if (entity_tag == _config.tag_id) {
        return true;
      }
    }

    return false;
  }

  // Accessor for pre-filtering (e.g., EventScheduler)
  int tag_id() const {
    return _config.tag_id;
  }

private:
  TagFilterConfig _config;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_TAG_FILTER_HPP_
