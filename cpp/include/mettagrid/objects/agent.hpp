#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_AGENT_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_AGENT_HPP_

#include <algorithm>
#include <array>
#include <cassert>
#include <random>
#include <string>
#include <vector>

#include "core/tag_index.hpp"
#include "core/types.hpp"
#include "handler/handler.hpp"
#include "handler/handler_context.hpp"
#include "objects/agent_config.hpp"
#include "objects/constants.hpp"
#include "systems/reward.hpp"
#include "systems/stats_tracker.hpp"

class ObservationEncoder;

class Agent : public GridObject {
public:
  ObservationType group;
  short frozen;
  short freeze_duration;
  // Role-conditioning token (0..3). Used for `agent:role` observations and role-gated rewards.
  uint8_t role = 255;
  // Soft role weights (0..255 per role: miner/aligner/scrambler/scout). Used for role-weight tokens and
  // scaling role-gated rewards.
  std::array<uint8_t, 4> role_weights = {0, 0, 0, 0};
  RewardHelper reward_helper;
  std::string group_name;
  // Despite being a GridObjectId, this is different from the `id` property.
  // This is the index into MettaGrid._agents (std::vector<Agent*>)
  GridObjectId agent_id;
  // Index within the agent's group (assigned at registration time).
  uint32_t group_index = 0;
  StatsTracker stats;
  GridLocation prev_location;
  GridLocation spawn_location;
  unsigned int steps_without_motion;
  std::vector<std::shared_ptr<mettagrid::Handler>> _on_tick;
  void set_on_tick(std::vector<std::shared_ptr<mettagrid::Handler>> handlers);
  void apply_on_tick(mettagrid::HandlerContext& ctx);

  // Vibe prediction: track when vibe was last set
  unsigned int vibe_set_step = 0;

  // Pointer to MettaGrid's current_step for vibe timestamp tracking
  const unsigned int* current_step_ptr = nullptr;

  Agent(GridCoord r, GridCoord c, const AgentConfig& config, const std::vector<std::string>* resource_names);

  void init(RewardType* reward_ptr);
  void init_reward(StatsTracker* game_stats,
                   mettagrid::TagIndex* tag_index,
                   const std::vector<std::string>* resource_names);

  void populate_initial_inventory(const std::unordered_map<InventoryItem, InventoryQuantity>& initial_inventory);

  void set_inventory(const std::unordered_map<InventoryItem, InventoryQuantity>& inventory);

  void on_inventory_change(InventoryItem item, InventoryDelta delta) override;

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

  const std::vector<uint8_t>& get_role_order() const {
    return role_order;
  }

  const std::vector<std::vector<uint8_t>>& get_role_mix_order() const {
    return role_mix_order;
  }

private:
  const ObservationEncoder* obs_encoder = nullptr;
  std::vector<uint8_t> role_order;
  std::vector<std::vector<uint8_t>> role_mix_order;
};

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_AGENT_HPP_
