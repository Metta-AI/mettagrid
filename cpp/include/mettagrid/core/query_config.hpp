#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_QUERY_CONFIG_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_QUERY_CONFIG_HPP_

#include <memory>
#include <vector>

#include "core/filter_config.hpp"

class GridObject;

namespace mettagrid {

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

// TagQueryConfig: Find objects with a specific tag, optionally filtered.
struct TagQueryConfig : public QueryConfig {
  int tag_id = -1;
  std::vector<FilterConfig> filters;
  std::vector<GridObject*> evaluate(const QuerySystem& system) const override;
};

// Query Tag Config - Tags computed by queries
struct QueryTagConfig {
  int tag_id = -1;
  std::shared_ptr<QueryConfig> query;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_QUERY_CONFIG_HPP_
