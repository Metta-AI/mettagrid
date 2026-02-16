#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_QUERY_SYSTEM_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_QUERY_SYSTEM_HPP_

#include <memory>
#include <random>
#include <vector>

#include "core/filter_config.hpp"
#include "core/query_config.hpp"

// Forward declarations
class Grid;
class GridObject;

namespace mettagrid {

class TagIndex;
class Filter;

/**
 * QuerySystem - Computes query tags from QueryConfig definitions.
 *
 * Supports TagQuery and ClosureQuery (with MaxDistance filters).
 * Recomputation is explicit via recompute(tag_id), triggered by
 * RecomputeQueryTagMutation.
 */
class QuerySystem {
public:
  QuerySystem(Grid* grid, TagIndex* tag_index, std::mt19937* rng, const std::vector<QueryTagConfig>& configs);

  // Compute all query tags from scratch (called at init)
  void compute_all();

  // Recompute a specific query tag (called by RecomputeQueryTagMutation)
  void recompute(int tag_id);

  // Public accessors for use by QueryConfig::evaluate() implementations
  Grid* grid() const {
    return _grid;
  }
  TagIndex* tag_index() const {
    return _tag_index;
  }

  // Apply max_items / order_by post-processing
  std::vector<GridObject*> apply_limits(std::vector<GridObject*> results, int max_items, QueryOrderBy order_by) const;

  // Check if an object passes all filter configs
  bool matches_filters(GridObject* obj, const std::vector<FilterConfig>& filter_configs) const;

private:
  struct QueryTagDef {
    int tag_id;
    std::shared_ptr<QueryConfig> query;
  };

  Grid* _grid;
  TagIndex* _tag_index;
  std::mt19937* _rng;
  std::vector<QueryTagDef> _query_tags;
  bool _computing = false;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_QUERY_SYSTEM_HPP_
