#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_AGENT_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_AGENT_HPP_

#include <algorithm>
#include <array>
#include <cassert>
#include <random>
#include <string>
#include <vector>

#include "core/types.hpp"
#include "objects/agent_config.hpp"
#include "objects/constants.hpp"
#include "systems/stats_tracker.hpp"

class ObservationEncoder;

class Agent : public GridObject {
public:
  ObservationType group;
  short frozen;
  short freeze_duration;
  // inventory is a map of item to amount.
  // keys should be deleted when the amount is 0, to keep iteration faster.
  // however, this should not be relied on for correctness.
  std::unordered_map<std::string, RewardType> stat_rewards;
  std::unordered_map<std::string, RewardType> stat_reward_max;
  std::string group_name;
  // Despite being a GridObjectId, this is different from the `id` property.
  // This is the index into MettaGrid._agents (std::vector<Agent*>)
  GridObjectId agent_id;
  StatsTracker stats;
  RewardType current_stat_reward;
  RewardType* reward;
  GridLocation prev_location;
  GridLocation spawn_location;
  unsigned int steps_without_motion;
  // Vibe-dependent inventory regeneration: vibe_id -> resource_id -> amount (can be negative for decay)
  // Vibe ID 0 ("default") is used as fallback when agent's current vibe is not found
  std::unordered_map<ObservationType, std::unordered_map<InventoryItem, InventoryDelta>> inventory_regen_amounts;

  // Vibe prediction: track when vibe was last set
  unsigned int vibe_set_step = 0;

  // Pointer to MettaGrid's current_step for vibe timestamp tracking
  const unsigned int* current_step_ptr = nullptr;

  Agent(GridCoord r, GridCoord c, const AgentConfig& config, const std::vector<std::string>* resource_names);

  void init(RewardType* reward_ptr);

  void populate_initial_inventory(const std::unordered_map<InventoryItem, InventoryQuantity>& initial_inventory);

  void set_inventory(const std::unordered_map<InventoryItem, InventoryQuantity>& inventory);

  void on_inventory_change(InventoryItem item, InventoryDelta delta) override;

  void compute_stat_rewards(StatsTracker* game_stats_tracker = nullptr);

  // Implementation of Usable interface
  bool onUse(Agent& actor, ActionArg arg) override;

  std::vector<PartialObservationToken> obs_features() const override;

  // Set observation encoder for inventory feature ID lookup
  void set_obs_encoder(const ObservationEncoder* encoder) {
    this->obs_encoder = encoder;
  }

  // Set pointer to current step for vibe timestamp tracking
  void set_current_step_ptr(const unsigned int* step_ptr) {
    this->current_step_ptr = step_ptr;
  }

private:
  const ObservationEncoder* obs_encoder = nullptr;
};

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_AGENT_HPP_
