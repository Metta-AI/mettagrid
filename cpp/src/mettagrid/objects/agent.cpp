#include "objects/agent.hpp"

#include <algorithm>
#include <cstdlib>

#include "config/observation_features.hpp"

// For std::shuffle
#include <random>

Agent::Agent(GridCoord r, GridCoord c, const AgentConfig& config, const std::vector<std::string>* resource_names)
    : GridObject(config.inventory_config),
      group(config.group_id),
      reward_helper(config.reward_config),
      group_name(config.group_name),
      agent_id(0),
      stats(resource_names),
      prev_location(r, c),
      spawn_location(r, c),
      steps_without_motion(0) {
  populate_initial_inventory(config.initial_inventory);
  GridObject::init(config.type_id, config.type_name, GridLocation(r, c), config.tag_ids, config.initial_vibe);
}

void Agent::init(RewardType* reward_ptr) {
  this->reward_helper.init(reward_ptr);
  reset_coverage_tracking();
}

void Agent::init_reward(const mettagrid::HandlerContext& game_ctx) {
  mettagrid::HandlerContext reward_ctx = game_ctx;
  reward_ctx.actor = this;
  reward_ctx.target = this;
  this->reward_helper.init_entries(reward_ctx);
}

uint32_t Agent::pack_location(const GridLocation& location) {
  return (static_cast<uint32_t>(location.r) << 16) | static_cast<uint32_t>(location.c);
}

void Agent::reset_coverage_tracking() {
  unique_cells_visited.clear();
  max_distance_from_spawn = 0;
  unique_cells_visited.insert(pack_location(location));
  stats.set("cell.unique_visited", static_cast<float>(unique_cells_visited.size()));
  stats.set("cell.max_distance_from_spawn", 0.0f);
}

void Agent::track_coverage() {
  unique_cells_visited.insert(pack_location(location));
  stats.set("cell.unique_visited", static_cast<float>(unique_cells_visited.size()));

  int dc = static_cast<int>(location.c) - static_cast<int>(spawn_location.c);
  int dr = static_cast<int>(spawn_location.r) - static_cast<int>(location.r);
  max_distance_from_spawn = std::max(max_distance_from_spawn, static_cast<uint32_t>(std::abs(dr) + std::abs(dc)));
  stats.set("cell.max_distance_from_spawn", static_cast<float>(max_distance_from_spawn));
}

void Agent::set_on_tick(std::shared_ptr<mettagrid::Handler> handler) {
  _on_tick = std::move(handler);
}

void Agent::apply_on_tick(mettagrid::HandlerContext& ctx) {
  if (_on_tick) {
    _on_tick->try_apply(ctx);
  }
}

void Agent::populate_initial_inventory(const std::unordered_map<InventoryItem, InventoryQuantity>& initial_inventory) {
  for (const auto& [item, amount] : initial_inventory) {
    this->inventory.update(item, amount, /*ignore_limits=*/true, /*notify=*/false);
    this->stats.set(this->stats.resource_name(item) + ".amount", static_cast<float>(amount));
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

    // Emit death stat when HP drops to 0
    if (amount == 0 && delta < 0 && this->stats.resource_name(item) == "hp") {
      this->stats.add("death", 1);
    }
  }
}

bool Agent::onUse(Agent& actor, ActionArg arg, const mettagrid::HandlerContext& ctx) {
  return GridObject::onUse(actor, arg, ctx);
}

std::vector<PartialObservationToken> Agent::obs_features() const {
  auto features = GridObject::obs_features();

  // Agent-specific observations
  features.push_back({ObservationFeature::Group, static_cast<ObservationType>(group)});
  features.push_back({ObservationFeature::AgentId, static_cast<ObservationType>(agent_id)});

  return features;
}

size_t Agent::max_obs_features(size_t max_tags, size_t num_resources, size_t tokens_per_item) {
  // GridObject features + 2 agent-specific (group, agent_id)
  return GridObject::max_obs_features(max_tags, num_resources, tokens_per_item) + 2;
}

size_t Agent::write_obs_features(PartialObservationToken* out, size_t max_tokens) const {
  size_t written = GridObject::write_obs_features(out, max_tokens);

  // Agent-specific observations
  if (written < max_tokens) {
    out[written++] = {ObservationFeature::Group, static_cast<ObservationType>(group)};
  }
  if (written < max_tokens) {
    out[written++] = {ObservationFeature::AgentId, static_cast<ObservationType>(agent_id)};
  }

  return written;
}
