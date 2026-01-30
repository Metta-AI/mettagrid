#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_HANDLER_CONFIG_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_HANDLER_CONFIG_HPP_

#include <memory>
#include <string>
#include <variant>
#include <vector>

#include "core/game_value_config.hpp"
#include "core/types.hpp"

namespace mettagrid {

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

// Align-to options for AlignmentMutation
enum class AlignTo {
  actor_collective,  // Align target to actor's collective
  none               // Remove target's collective alignment
};

// Handler types
enum class HandlerType {
  on_use,  // Triggered when agent uses/activates the object
  aoe      // Triggered per-tick for objects within radius
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

struct GameValueFilterConfig {
  GameValueConfig value;
  float threshold = 0.0f;
  EntityRef entity = EntityRef::target;
};

// Forward declaration for recursive filter config
struct NearFilterConfig;

// Variant type for all filter configs (defined early so NearFilterConfig can reference it)
using FilterConfig = std::variant<VibeFilterConfig,
                                  ResourceFilterConfig,
                                  AlignmentFilterConfig,
                                  TagFilterConfig,
                                  NearFilterConfig,
                                  GameValueFilterConfig>;

struct NearFilterConfig {
  EntityRef entity = EntityRef::target;
  std::vector<FilterConfig> filters;  // Filters that nearby objects must pass (can include nested NearFilter)
  int radius = 1;                     // Radius (chebyshev distance) to check
  int target_tag = -1;                // Tag ID to find nearby objects with
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
  float delta = 0.0f;
  EntityRef entity = EntityRef::target;
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
                                    GameValueMutationConfig>;

// ============================================================================
// Handler Config
// ============================================================================

struct HandlerConfig {
  std::string name;
  std::vector<FilterConfig> filters;      // All must pass for handler to trigger
  std::vector<MutationConfig> mutations;  // Applied sequentially if filters pass

  // AOE-specific fields (only used for aoe handlers)
  int radius = 0;  // L-infinity (Chebyshev) distance for AOE

  HandlerConfig() = default;
  explicit HandlerConfig(const std::string& handler_name) : name(handler_name) {}
};

// ============================================================================
// AOE Config - Unified configuration for Area of Effect systems
// ============================================================================

// Resource delta for presence_deltas (applied on enter/exit)
struct ResourceDelta {
  InventoryItem resource_id = 0;
  InventoryDelta delta = 0;
};

/**
 * AOEConfig - Configuration for Area of Effect (AOE) systems.
 *
 * Inherits filters and mutations from HandlerConfig.
 *
 * Supports two modes:
 * - Static (is_static=true, default): Pre-computed cell registration for efficiency.
 *   Good for stationary objects like turrets, healing stations.
 * - Mobile (is_static=false): Re-evaluated each tick for moving sources.
 *   Good for agents with auras.
 *
 * In AOE context, "actor" refers to the AOE source object and "target" refers to
 * the affected object.
 */
struct AOEConfig : public HandlerConfig {
  bool is_static = true;     // true = fixed (default), false = mobile (for agents)
  bool effect_self = false;  // Whether source is affected by its own AOE

  // One-time resource changes when target enters/exits AOE
  // Enter: apply +delta, Exit: apply -delta
  std::vector<ResourceDelta> presence_deltas;

  AOEConfig() {
    radius = 1;  // Override default radius for AOE
  }
};

// ============================================================================
// Event Config - Timestep-based events
// ============================================================================

/**
 * EventConfig - Configuration for timestep-based events.
 *
 * Events fire at specified timesteps and apply mutations to all objects
 * that pass the configured filters. Unlike handlers (triggered by actions)
 * or AOE (triggered by proximity), events are triggered by the game clock.
 */
struct EventConfig {
  std::string name;                       // Unique name for this event
  int target_tag_id = -1;                 // Tag ID for finding targets via TagIndex (required)
  std::vector<int> timesteps;             // Timesteps when this event fires
  std::vector<FilterConfig> filters;      // All must pass for event to affect object
  std::vector<MutationConfig> mutations;  // Applied to matching objects
  int max_targets = 0;                    // Maximum targets to apply to (0 = unlimited)
  std::string fallback;                   // Event name to fire if no targets match (optional)

  EventConfig() = default;
  explicit EventConfig(const std::string& event_name) : name(event_name) {}
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_HANDLER_CONFIG_HPP_
