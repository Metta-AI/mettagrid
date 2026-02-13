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

// Entity reference for resolving actor/target in filters and mutations
enum class EntityRef {
  actor,             // The object performing the action (or source for AOE)
  target,            // The object being affected
  actor_collective,  // The collective of the actor
  target_collective  // The collective of the target
};

// Alignment conditions for AlignmentFilter
enum class AlignmentCondition {
  aligned,              // Entity has a collective
  unaligned,            // Entity has no collective
  same_collective,      // Actor and target belong to same collective
  different_collective  // Actor and target belong to different collectives
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

struct AlignmentFilterConfig {
  EntityRef entity = EntityRef::target;  // Which entity to check
  AlignmentCondition condition = AlignmentCondition::same_collective;
  int collective_id = -1;  // If >= 0, check if entity belongs to this specific collective
};

struct TagFilterConfig {
  EntityRef entity = EntityRef::target;
  int tag_id = 0;  // Single tag ID that must be present on the object
};

struct SharedTagPrefixFilterConfig {
  std::vector<int> tag_ids;  // All tag IDs sharing the prefix (resolved at config time)
};

struct GameValueFilterConfig {
  GameValueConfig value;
  float threshold = 0.0f;
  EntityRef entity = EntityRef::target;
};

// Forward declarations for recursive filter configs
struct NearFilterConfig;
struct NegFilterConfig;
struct OrFilterConfig;
struct MaxDistanceFilterConfig;

// Variant type for all filter configs (defined early so NearFilterConfig/NegFilterConfig can reference it)
using FilterConfig = std::variant<VibeFilterConfig,
                                  ResourceFilterConfig,
                                  AlignmentFilterConfig,
                                  TagFilterConfig,
                                  SharedTagPrefixFilterConfig,
                                  NearFilterConfig,
                                  GameValueFilterConfig,
                                  NegFilterConfig,
                                  OrFilterConfig,
                                  MaxDistanceFilterConfig>;

struct NearFilterConfig {
  EntityRef entity = EntityRef::target;
  std::vector<FilterConfig> filters;  // Filters that nearby objects must pass (can include nested NearFilter)
  int radius = 1;                     // Radius (chebyshev distance) to check
  int target_tag = -1;                // Tag ID to find nearby objects with
};

// NegFilterConfig: Wraps filter config(s) and negates the ANDed result.
// Multiple inner filters are ANDed together first, then negated.
// This implements NOT(A AND B AND ...) semantics, critical for multi-resource filters.
// Uses a vector to break the recursive type (same pattern as NearFilterConfig).
struct NegFilterConfig {
  std::vector<FilterConfig> inner;  // Filters to AND together, then negate
};

// OrFilterConfig: Wraps filter configs and ORs them together.
// Passes if ANY of the inner filters pass.
struct OrFilterConfig {
  std::vector<FilterConfig> inner;  // Filters to OR together
};

// MaxDistanceFilterConfig: Checks if entity is within radius of any source query result.
// Works in both handler context (using entity ref) and query context (actor=target=candidate).
struct MaxDistanceFilterConfig {
  EntityRef entity = EntityRef::target;  // Entity to check distance from (handler context)
  std::shared_ptr<QueryConfig> source;   // Source query to check distance from
  unsigned int radius = 0;               // Max Chebyshev distance (0 = unlimited)
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_FILTER_CONFIG_HPP_
