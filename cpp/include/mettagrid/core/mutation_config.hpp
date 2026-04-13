#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_MUTATION_CONFIG_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_MUTATION_CONFIG_HPP_

#include <memory>
#include <string>
#include <utility>
#include <variant>
#include <vector>

#include "core/filter_config.hpp"
#include "core/game_value_config.hpp"
#include "core/types.hpp"

namespace mettagrid {

// Forward declaration
struct QueryConfig;

// Target for stats logging - which stats tracker to log to
enum class StatsTarget {
  game,  // Log to game-level stats tracker
  agent  // Log to entity's agent stats tracker
};

// Which entity to use for resolving stats target
enum class StatsEntity {
  target,  // Use the target entity (default)
  actor    // Use the actor entity
};

// ============================================================================
// Mutation Configs
// ============================================================================

struct ResourceDeltaMutationConfig {
  EntityRef entity = EntityRef::target;
  InventoryItem resource_id = 0;
  InventoryDelta delta = 0;
};

struct ResourceTransferMutationConfig {
  EntityRef source = EntityRef::actor;
  EntityRef destination = EntityRef::target;
  InventoryItem resource_id = 0;
  InventoryDelta amount = -1;             // -1 means transfer all available
  bool remove_source_when_empty = false;  // Remove source from grid when its inventory is empty
};

struct ClearInventoryMutationConfig {
  EntityRef entity = EntityRef::target;
  // List of resource IDs to clear. If empty, clears all resources.
  std::vector<InventoryItem> resource_ids;
};

struct AttackMutationConfig {
  InventoryItem weapon_resource = 0;
  InventoryItem armor_resource = 0;
  InventoryItem health_resource = 0;
  int damage_multiplier_pct = 100;  // Percentage (100 = 1.0x, 150 = 1.5x)
};

struct StatsMutationConfig {
  std::string stat_name;                     // Name of the stat to set
  StatsTarget target = StatsTarget::game;    // Which stats tracker to set
  StatsEntity entity = StatsEntity::target;  // Which entity to use for resolving target
  GameValueConfig source;                    // Game value expression to compute the new stat value
};

struct AddTagMutationConfig {
  EntityRef entity = EntityRef::target;
  int tag_id = -1;
};

struct RemoveTagMutationConfig {
  EntityRef entity = EntityRef::target;
  int tag_id = -1;
};

struct ChangeVibeMutationConfig {
  EntityRef entity = EntityRef::target;
  ObservationType vibe_id = 0;
};

struct GameValueMutationConfig {
  GameValueConfig value;
  EntityRef target = EntityRef::target;
  GameValueConfig source;  // Source of the delta (CONST for static, or any GameValue for dynamic)
};

struct RecomputeMaterializedQueryMutationConfig {
  int tag_id = -1;
};

struct QueryInventoryMutationConfig {
  std::shared_ptr<QueryConfig> query;
  std::vector<std::pair<InventoryItem, InventoryDelta>> deltas;
  EntityRef source = EntityRef::actor;  // Only used if has_source=true
  bool has_source = false;              // Transfer mode

  // Optional: log actual transfer amounts to game stats.
  // Maps resource_id -> stat_name. When present, logs the actual transferred amount.
  std::vector<std::pair<InventoryItem, std::string>> transfer_stat_names;
};

struct RemoveTagsWithPrefixMutationConfig {
  EntityRef entity = EntityRef::target;
  std::vector<int> tag_ids;  // All tag IDs sharing the prefix (resolved at config time)
};

struct RelocateMutationConfig {};   // Move actor to target cell
struct SwapMutationConfig {};       // Swap actor and target positions
struct UseTargetMutationConfig {};  // Delegate to target's onUse handler

struct SpawnObjectMutationConfig {
  std::string object_type;  // Object type name to spawn at target_location
};

// RaycastSpawnMutation: Walk rays from target and spawn objects at empty cells.
// Stops each ray at the first object matching any blocker filter.
struct RaycastSpawnMutationConfig {
  std::string object_type;                             // Object type to spawn
  std::vector<std::pair<int, int>> directions;         // (dr, dc) pairs for each ray direction
  GameValueConfig max_range = ConstValueConfig{2.0f};  // Max cells per arm, supports runtime GameValue
  std::vector<FilterConfig> blocker;                   // Filters that identify blocking objects
};

// Variant type for all mutation configs
using MutationConfig = std::variant<ResourceDeltaMutationConfig,
                                    ResourceTransferMutationConfig,
                                    ClearInventoryMutationConfig,
                                    AttackMutationConfig,
                                    StatsMutationConfig,
                                    AddTagMutationConfig,
                                    RemoveTagMutationConfig,
                                    GameValueMutationConfig,
                                    RecomputeMaterializedQueryMutationConfig,
                                    QueryInventoryMutationConfig,
                                    RemoveTagsWithPrefixMutationConfig,
                                    RelocateMutationConfig,
                                    SwapMutationConfig,
                                    UseTargetMutationConfig,
                                    SpawnObjectMutationConfig,
                                    RaycastSpawnMutationConfig,
                                    ChangeVibeMutationConfig>;

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_MUTATION_CONFIG_HPP_
