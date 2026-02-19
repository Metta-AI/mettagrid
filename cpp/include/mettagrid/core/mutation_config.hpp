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

// Align-to options for AlignmentMutation
enum class AlignTo {
  actor_collective,  // Align target to actor's collective
  none               // Remove target's collective alignment
};

// Target for stats logging - which stats tracker to log to
enum class StatsTarget {
  game,       // Log to game-level stats tracker
  agent,      // Log to entity's agent stats tracker
  collective  // Log to entity's collective's stats tracker
};

// Which entity to use for resolving stats target (agent or collective)
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

struct AlignmentMutationConfig {
  AlignTo align_to = AlignTo::actor_collective;
  std::string collective_name;  // If non-empty, align to this specific collective (overrides align_to)
  int collective_id = -1;       // Resolved collective ID (set during config setup)
};

struct FreezeMutationConfig {
  int duration = 1;  // Ticks to freeze
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
  std::string stat_name;                         // Name of the stat to log
  float delta = 1.0f;                            // Delta to add to the stat
  StatsTarget target = StatsTarget::collective;  // Which stats tracker to log to
  StatsEntity entity = StatsEntity::target;      // Which entity to use for resolving target
};

struct AddTagMutationConfig {
  EntityRef entity = EntityRef::target;
  int tag_id = -1;
};

struct RemoveTagMutationConfig {
  EntityRef entity = EntityRef::target;
  int tag_id = -1;
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
};

struct RemoveTagsWithPrefixMutationConfig {
  EntityRef entity = EntityRef::target;
  std::vector<int> tag_ids;  // All tag IDs sharing the prefix (resolved at config time)
};

// Variant type for all mutation configs
using MutationConfig = std::variant<ResourceDeltaMutationConfig,
                                    ResourceTransferMutationConfig,
                                    AlignmentMutationConfig,
                                    FreezeMutationConfig,
                                    ClearInventoryMutationConfig,
                                    AttackMutationConfig,
                                    StatsMutationConfig,
                                    AddTagMutationConfig,
                                    RemoveTagMutationConfig,
                                    GameValueMutationConfig,
                                    RecomputeMaterializedQueryMutationConfig,
                                    QueryInventoryMutationConfig,
                                    RemoveTagsWithPrefixMutationConfig>;

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_MUTATION_CONFIG_HPP_
