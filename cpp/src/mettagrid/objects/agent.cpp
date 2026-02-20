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
      reward_helper(config.reward_config),
      group_name(config.group_name),
      agent_id(0),
      stats(resource_names),
      prev_location(r, c),
      spawn_location(r, c),
      steps_without_motion(0),
      _log_sum_stats(config.log_sum_stats) {
  for (size_t i = 0; i < _log_sum_stats.size(); ++i) {
    for (auto item : _log_sum_stats[i].items) {
      _item_to_log_sum_indices[item].push_back(i);
    }
  }
  populate_initial_inventory(config.initial_inventory);
  GridObject::init(config.type_id, config.type_name, GridLocation(r, c), config.tag_ids, config.initial_vibe);
}

void Agent::init(RewardType* reward_ptr) {
  this->reward_helper.init(reward_ptr);
}

void Agent::init_reward(StatsTracker* collective_stats,
                        const mettagrid::HandlerContext* game_ctx,
                        const std::vector<std::string>* resource_names) {
  this->reward_helper.init_entries(&this->stats, collective_stats, game_ctx, resource_names);
}

void Agent::set_on_tick(std::vector<std::shared_ptr<mettagrid::Handler>> handlers) {
  _on_tick = std::move(handlers);
}

void Agent::apply_on_tick(mettagrid::HandlerContext& ctx) {
  for (auto& handler : _on_tick) {
    handler->try_apply(ctx);
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

    auto it = _item_to_log_sum_indices.find(item);
    if (it != _item_to_log_sum_indices.end()) {
      for (size_t idx : it->second) {
        _recompute_log_sum(_log_sum_stats[idx]);
      }
    }
  }
}

void Agent::_recompute_log_sum(const LogSumStatConfig& cfg) {
  float sum = 0.0f;
  for (auto item : cfg.items) {
    float val = stats.get(stats.resource_name(item) + cfg.stat_suffix);
    sum += std::log(val + 1.0f);
  }
  stats.set(cfg.stat_name, sum);
}

bool Agent::onUse(Agent& actor, ActionArg arg, const mettagrid::HandlerContext& ctx) {
  // Agent-to-agent transfers are now handled by the Transfer action handler.
  // This method returns false to indicate no default use action.
  (void)actor;
  (void)arg;
  (void)ctx;
  return false;
}

std::vector<PartialObservationToken> Agent::obs_features() const {
  // Start with base class features (collective, tags, vibe, inventory)
  auto features = GridObject::obs_features();

  // Agent-specific observations
  features.push_back({ObservationFeature::Group, static_cast<ObservationType>(group)});
  features.push_back({ObservationFeature::Frozen, static_cast<ObservationType>(frozen != 0 ? 1 : 0)});
  features.push_back({ObservationFeature::AgentId, static_cast<ObservationType>(agent_id)});

  return features;
}

size_t Agent::max_obs_features(size_t max_tags, size_t num_resources, size_t tokens_per_item) {
  // GridObject features + 3 agent-specific (group, frozen, agent_id)
  return GridObject::max_obs_features(max_tags, num_resources, tokens_per_item) + 3;
}

size_t Agent::write_obs_features(PartialObservationToken* out, size_t max_tokens) const {
  // Start with base class features (collective, tags, vibe, inventory)
  size_t written = GridObject::write_obs_features(out, max_tokens);

  // Agent-specific observations
  if (written < max_tokens) {
    out[written++] = {ObservationFeature::Group, static_cast<ObservationType>(group)};
  }
  if (written < max_tokens) {
    out[written++] = {ObservationFeature::Frozen, static_cast<ObservationType>(frozen != 0 ? 1 : 0)};
  }
  if (written < max_tokens) {
    out[written++] = {ObservationFeature::AgentId, static_cast<ObservationType>(agent_id)};
  }

  return written;
}
