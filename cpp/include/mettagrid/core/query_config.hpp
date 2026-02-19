#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_QUERY_CONFIG_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_QUERY_CONFIG_HPP_

#include <memory>
#include <vector>

#include "core/filter_config.hpp"

// Forward declarations for query evaluate()
class Grid;
class GridObject;

namespace mettagrid {

// Forward declaration for QuerySystem (used by QueryConfig::evaluate)
class QuerySystem;

// Order-by for query results
enum class QueryOrderBy {
  none,   // No ordering (default)
  random  // Shuffle results randomly
};

// Base class for query configs. Subclasses implement evaluate() to return matching objects.
struct QueryConfig {
  int max_items = 0;  // 0 = unlimited
  QueryOrderBy order_by = QueryOrderBy::none;
  virtual ~QueryConfig() = default;
  virtual std::vector<GridObject*> evaluate(const QuerySystem& system) const = 0;
};

// Opaque holder for QueryConfig - wraps shared_ptr<QueryConfig> for pybind11 interop.
struct QueryConfigHolder {
  std::shared_ptr<QueryConfig> config;
};

// ============================================================================
// Concrete Query Configs
// ============================================================================

// TagQueryConfig: Find objects with a specific tag, optionally filtered.
struct TagQueryConfig : public QueryConfig {
  int tag_id = -1;
  std::vector<FilterConfig> filters;
  std::vector<GridObject*> evaluate(const QuerySystem& system) const override;
};

// ClosureQueryConfig: BFS from source through edge_filter-filtered neighbors.
struct ClosureQueryConfig : public QueryConfig {
  std::shared_ptr<QueryConfig> source;       // root query
  std::vector<FilterConfig> edge_filter;     // filters applied to neighbors for BFS expansion
  std::vector<FilterConfig> result_filters;  // filters applied to result set (e.g. junction-only)
  unsigned int radius = 0;                   // Chebyshev expansion distance (0 = unlimited)
  std::vector<GridObject*> evaluate(const QuerySystem& system) const override;
};

// ============================================================================
// Materialized Query Tag - Tags computed by queries
// ============================================================================

struct MaterializedQueryTag {
  int tag_id = -1;
  std::shared_ptr<QueryConfig> query;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_QUERY_CONFIG_HPP_
