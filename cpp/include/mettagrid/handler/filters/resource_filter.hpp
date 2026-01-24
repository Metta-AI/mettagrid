#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_RESOURCE_FILTER_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_RESOURCE_FILTER_HPP_

#include "handler/filters/filter.hpp"
#include "handler/handler_config.hpp"

namespace mettagrid {

/**
 * ResourceFilter: Check if entity has minimum resources
 */
class ResourceFilter : public Filter {
public:
  explicit ResourceFilter(const ResourceFilterConfig& config) : _config(config) {}

  bool passes(const HandlerContext& ctx) const override {
    HasInventory* entity = ctx.resolve(_config.entity);
    if (entity == nullptr) {
      return false;
    }

    return entity->inventory.amount(_config.resource_id) >= _config.min_amount;
  }

private:
  ResourceFilterConfig _config;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_RESOURCE_FILTER_HPP_
