#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_TAG_FILTER_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_TAG_FILTER_HPP_

#include "core/grid_object.hpp"
#include "handler/filters/filter.hpp"
#include "handler/handler_config.hpp"

namespace mettagrid {

class TagFilter : public Filter {
public:
  explicit TagFilter(const TagFilterConfig& config) : _config(config) {}

  bool passes(const HandlerContext& ctx) const override {
    GridObject* grid_obj = dynamic_cast<GridObject*>(ctx.resolve(_config.entity));
    if (grid_obj == nullptr) {
      return false;
    }
    return grid_obj->has_tag(_config.tag_id);
  }

public:
  int tag_id() const {
    return _config.tag_id;
  }

private:
  TagFilterConfig _config;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_TAG_FILTER_HPP_
