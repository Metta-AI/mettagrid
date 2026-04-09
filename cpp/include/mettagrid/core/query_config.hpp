#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_QUERY_CONFIG_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_QUERY_CONFIG_HPP_

#include <memory>
#include <vector>

#include "core/filter_config.hpp"

// Forward declarations for query evaluate()
class GridObject;

namespace mettagrid {

class HandlerContext;

// Order-by for query results
enum class QueryOrderBy {
  none,   // No ordering (default)
  random  // Shuffle results randomly
};

// Base class for query configs. Subclasses implement evaluate() to return matching objects.
struct QueryConfig {
  int max_items = -1;  // -1 = unlimited
  QueryOrderBy order_by = QueryOrderBy::none;
  virtual ~QueryConfig() = default;
  virtual std::vector<GridObject*> evaluate(const HandlerContext& ctx) const = 0;
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
  std::vector<GridObject*> evaluate(const HandlerContext& ctx) const override;
};

// ClosureQueryConfig: BFS from source through candidates connected by edge filters.
// Source query finds seed objects, candidates query finds the pool, edge_filters
// are binary filters evaluated with (net_member, candidate) context per hop.
struct ClosureQueryConfig : public QueryConfig {
  std::shared_ptr<QueryConfig> source;       // seed query
  std::shared_ptr<QueryConfig> candidates;   // candidate pool query
  std::vector<FilterConfig> edge_filters;    // binary: (net_member, candidate)
  std::vector<FilterConfig> result_filters;  // unary: applied to final result set
  std::vector<GridObject*> evaluate(const HandlerContext& ctx) const override;
};

// FilteredQueryConfig: Evaluate a sub-query, then apply filters and limits to its results.
// This is the recursive composition primitive: Query(source=inner_query, filters=[...]).
struct FilteredQueryConfig : public QueryConfig {
  std::shared_ptr<QueryConfig> source;  // inner query to evaluate first
  std::vector<FilterConfig> filters;    // filters applied to inner query results
  std::vector<GridObject*> evaluate(const HandlerContext& ctx) const override;
};

// RaycastQueryConfig: Walk rays from source objects, collect objects on unblocked rays.
// Directions are (dr, dc) pairs; empty defaults to N/S/E/W.
// Blocker filters identify objects that stop a ray (OR semantics).
// include_blocker controls whether the first blocker itself is returned.
struct RaycastQueryConfig : public QueryConfig {
  std::shared_ptr<QueryConfig> source;          // Query to find ray origin objects
  unsigned int max_range = 2;                   // Max cells per arm
  std::vector<std::pair<int, int>> directions;  // (dr, dc) pairs; empty = all 4 cardinals
  std::vector<FilterConfig> blocker;            // Filters that identify blocking objects
  bool include_blocker = true;                  // Whether first blocker is included in results
  std::vector<GridObject*> evaluate(const HandlerContext& ctx) const override;
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
