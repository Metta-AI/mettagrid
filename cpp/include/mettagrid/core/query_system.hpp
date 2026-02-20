#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_QUERY_SYSTEM_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_QUERY_SYSTEM_HPP_

#include <memory>
#include <vector>

#include "core/filter_config.hpp"
#include "core/query_config.hpp"

// Forward declarations
class Grid;
class GridObject;

namespace mettagrid {

class HandlerContext;
class TagIndex;
class Filter;

/**
 * QuerySystem - Computes query tags from QueryConfig definitions.
 *
 * Supports TagQuery and ClosureQuery (with MaxDistance filters).
 * Recomputation is explicit via recompute(tag_id), triggered by
 * RecomputeMaterializedQueryMutation.
 */
class QuerySystem {
public:
  explicit QuerySystem(const std::vector<MaterializedQueryTag>& configs);

  // Compute all query tags from scratch (called at init)
  void compute_all(const HandlerContext& ctx);

  // Recompute a specific query tag (called by RecomputeMaterializedQueryMutation)
  void recompute(int tag_id, const HandlerContext& ctx);

  // Apply max_items / order_by post-processing
  static std::vector<GridObject*> apply_limits(std::vector<GridObject*> results,
                                               int max_items,
                                               QueryOrderBy order_by,
                                               const HandlerContext& ctx);

  // Check if an object passes all filter configs
  static bool matches_filters(GridObject* obj,
                              const std::vector<FilterConfig>& filter_configs,
                              const HandlerContext& ctx);

private:
  struct QueryTagDef {
    int tag_id;
    std::shared_ptr<QueryConfig> query;
  };

  std::vector<QueryTagDef> _query_tags;
  bool _computing = false;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_QUERY_SYSTEM_HPP_
