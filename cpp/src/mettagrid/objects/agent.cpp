#include "objects/agent.hpp"

#include <algorithm>

#include "config/observation_features.hpp"
#include "objects/collective.hpp"

// For std::shuffle
#include <random>

Agent::Agent(GridCoord r, GridCoord c, const AgentConfig& config, const std::vector<std::string>* resource_names)
    : GridObject(config.inventory_config),
      group(config.group_id),
      frozen(0),
      freeze_duration(config.freeze_duration),
      reward_computer(config.reward_config),
      group_name(config.group_name),
      agent_id(0),
      stats(resource_names),
      prev_location(r, c),
      spawn_location(r, c),
      steps_without_motion(0),
      inventory_regen_amounts(config.inventory_regen_amounts) {
  populate_initial_inventory(config.initial_inventory);
  GridObject::init(config.type_id, config.type_name, GridLocation(r, c), config.tag_ids, config.initial_vibe);
}

void Agent::init(RewardType* reward_ptr) {
  this->reward_computer.init(reward_ptr);
}

void Agent::populate_initial_inventory(const std::unordered_map<InventoryItem, InventoryQuantity>& initial_inventory) {
  for (const auto& [item, amount] : initial_inventory) {
    this->inventory.update(item, amount, /*ignore_limits=*/true);
  }
}

void Agent::set_inventory(const std::unordered_map<InventoryItem, InventoryQuantity>& inventory) {
  // First, remove items that are not present in the provided inventory map
  // Make a copy of current item keys to avoid iterator invalidation
  std::vector<InventoryItem> existing_items;
  for (const auto& [existing_item, existing_amount] : this->inventory.get()) {
    existing_items.push_back(existing_item);
  }

  for (const auto& existing_item : existing_items) {
    const InventoryQuantity current_amount = this->inventory.amount(existing_item);
    this->inventory.update(existing_item, -static_cast<InventoryDelta>(current_amount));
    this->stats.set(this->stats.resource_name(existing_item) + ".amount", 0);
  }

  // Then, set provided items to their specified amounts
  for (const auto& [item, amount] : inventory) {
    this->inventory.update(item, amount - this->inventory.amount(item));
  }
}

void Agent::on_inventory_change(InventoryItem item, InventoryDelta delta) {
  const InventoryQuantity amount = this->inventory.amount(item);
  if (delta != 0) {
    if (delta > 0) {
      this->stats.add(this->stats.resource_name(item) + ".gained", delta);
    } else if (delta < 0) {
      this->stats.add(this->stats.resource_name(item) + ".lost", -delta);
    }
    this->stats.set(this->stats.resource_name(item) + ".amount", amount);
  }
}

void Agent::compute_stat_rewards(StatsTracker* game_stats_tracker, mettagrid::TagIndex* tag_index) {
  this->reward_computer.compute(&this->stats, game_stats_tracker, tag_index, this->getCollective());
}

bool Agent::onUse(Agent& actor, ActionArg arg) {
  // Agent-to-agent transfers are now handled by the Transfer action handler.
  // This method returns false to indicate no default use action.
  (void)actor;
  (void)arg;
  return false;
}

std::vector<PartialObservationToken> Agent::obs_features() const {
  // Start with base class features (collective, tags, vibe, inventory)
  auto features = GridObject::obs_features();

  // Agent-specific observations
  features.push_back({ObservationFeature::Group, static_cast<ObservationType>(group)});
  features.push_back({ObservationFeature::Frozen, static_cast<ObservationType>(frozen != 0 ? 1 : 0)});

  return features;
}
