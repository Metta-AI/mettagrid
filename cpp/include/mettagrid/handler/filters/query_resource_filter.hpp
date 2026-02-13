#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_QUERY_RESOURCE_FILTER_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_QUERY_RESOURCE_FILTER_HPP_

#include <cassert>
#include <cstdint>

#include "core/grid_object.hpp"
#include "core/query_system.hpp"
#include "handler/filters/filter.hpp"
#include "handler/handler_config.hpp"

namespace mettagrid {

/**
 * QueryResourceFilter: Check if objects found by query have minimum total resources.
 *
 * Evaluates the query via QuerySystem, sums inventory across all results,
 * and checks that all resource requirements are met.
 */
class QueryResourceFilter : public Filter {
public:
  explicit QueryResourceFilter(const QueryResourceFilterConfig& config) : _config(config) {
    assert(_config.query != nullptr && "QueryResourceFilter requires a non-null query");
  }

  bool passes(const HandlerContext& ctx) const override {
    assert(ctx.query_system && "QueryResourceFilter requires query_system in HandlerContext");

    auto results = _config.query->evaluate(*ctx.query_system);

    for (const auto& [resource_id, min_amount] : _config.requirements) {
      uint32_t total = 0;
      for (GridObject* obj : results) {
        total += obj->inventory.amount(resource_id);
        if (total >= min_amount) {
          break;
        }
      }
      if (total < min_amount) {
        return false;
      }
    }

    return true;
  }

private:
  QueryResourceFilterConfig _config;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_QUERY_RESOURCE_FILTER_HPP_
