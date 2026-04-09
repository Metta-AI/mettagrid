#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_FILTER_CONFIG_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_FILTER_CONFIG_HPP_

#include <memory>
#include <variant>
#include <vector>

#include "core/game_value_config.hpp"
#include "core/types.hpp"

namespace mettagrid {

// Forward declaration for filter configs that reference queries
struct QueryConfig;

// Entity reference for resolving actor/target/source in filters and mutations
enum class EntityRef {
  actor,   // The object performing the action
  target,  // The object being affected
  source   // BFS frontier node in closure queries (distinct from actor)
};

// ============================================================================
// Filter Configs
// ============================================================================

struct VibeFilterConfig {
  EntityRef entity = EntityRef::target;
  ObservationType vibe_id = 0;  // The vibe ID to match (index into vibe_names)
};

struct ResourceFilterConfig {
  EntityRef entity = EntityRef::target;
  InventoryItem resource_id = 0;
  InventoryQuantity min_amount = 1;
};

struct SharedTagPrefixFilterConfig {
  std::vector<int> tag_ids;  // All tag IDs sharing the prefix (resolved at config time)
};

struct TagPrefixFilterConfig {
  EntityRef entity = EntityRef::target;
  std::vector<int> tag_ids;  // All tag IDs sharing the prefix (resolved at config time)
};

struct GameValueFilterConfig {
  GameValueConfig value;
  GameValueConfig threshold = ConstValueConfig{0.0f};
  EntityRef entity = EntityRef::target;
};

struct TargetLocEmptyFilterConfig {};  // Target cell is empty (target == nullptr)
struct TargetIsUsableFilterConfig {};  // Target implements Usable interface

struct PeriodicFilterConfig {
  unsigned int period = 1;    // Passes every `period` timesteps
  unsigned int start_on = 0;  // First timestep to pass on
};

// Forward declarations for recursive filter configs
struct NegFilterConfig;
struct OrFilterConfig;
struct MaxDistanceFilterConfig;
struct QueryResourceFilterConfig;

// Variant type for all filter configs
using FilterConfig = std::variant<VibeFilterConfig,
                                  ResourceFilterConfig,
                                  SharedTagPrefixFilterConfig,
                                  TagPrefixFilterConfig,
                                  GameValueFilterConfig,
                                  NegFilterConfig,
                                  OrFilterConfig,
                                  MaxDistanceFilterConfig,
                                  QueryResourceFilterConfig,
                                  TargetLocEmptyFilterConfig,
                                  TargetIsUsableFilterConfig,
                                  PeriodicFilterConfig>;

// NegFilterConfig: Wraps filter config(s) and negates the ANDed result.
// Multiple inner filters are ANDed together first, then negated.
// This implements NOT(A AND B AND ...) semantics, critical for multi-resource filters.
struct NegFilterConfig {
  std::vector<FilterConfig> inner;  // Filters to AND together, then negate
};

// OrFilterConfig: Wraps filter configs and ORs them together.
// Passes if ANY of the inner filters pass.
struct OrFilterConfig {
  std::vector<FilterConfig> inner;  // Filters to OR together
};

// MaxDistanceFilterConfig: Checks if entity is within radius of any source query result.
struct MaxDistanceFilterConfig {
  EntityRef entity = EntityRef::target;  // Entity to check distance from (handler context)
  std::shared_ptr<QueryConfig> source;   // Source query to check distance from
  unsigned int radius = 0;               // Max L2 distance, compared as sum of squares (0 = unlimited)
};

// QueryResourceFilterConfig: Checks if objects found by query have minimum total resources.
struct QueryResourceFilterConfig {
  std::shared_ptr<QueryConfig> query;
  std::vector<std::pair<InventoryItem, InventoryQuantity>> requirements;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_FILTER_CONFIG_HPP_
