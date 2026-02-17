#include "core/grid_object.hpp"

#include <algorithm>
#include <cassert>

#include "config/observation_features.hpp"
#include "core/tag_index.hpp"
#include "handler/handler.hpp"
#include "handler/handler_context.hpp"
#include "handler/multi_handler.hpp"
#include "objects/agent.hpp"
#include "objects/collective.hpp"
#include "systems/observation_encoder.hpp"

// Constructor and destructor must be defined here where Handler is a complete type
GridObject::GridObject(const InventoryConfig& inv_config) : HasInventory(inv_config) {}

GridObject::~GridObject() = default;

void GridObject::init(TypeId object_type_id,
                      const std::string& object_type_name,
                      const GridLocation& object_location,
                      const std::vector<int>& tags,
                      ObservationType object_vibe,
                      const std::string& object_name) {
  this->type_id = object_type_id;
  this->type_name = object_type_name;
  this->name = object_name.empty() ? object_type_name : object_name;
  this->location = object_location;
  this->tag_bits.reset();
  for (int tag : tags) {
    if (tag < 0 || static_cast<size_t>(tag) >= kMaxTags) continue;
    this->tag_bits.set(tag);
  }
  this->vibe = object_vibe;
}

void GridObject::set_on_use_handler(std::shared_ptr<mettagrid::Handler> handler) {
  _on_use_handler = std::move(handler);
}

void GridObject::set_aoe_configs(std::vector<mettagrid::AOEConfig> configs) {
  _aoe_configs = std::move(configs);
}

void GridObject::set_on_tag_add(std::unordered_map<int, std::vector<std::shared_ptr<mettagrid::Handler>>> handlers) {
  _on_tag_add = std::move(handlers);
}

void GridObject::set_on_tag_remove(std::unordered_map<int, std::vector<std::shared_ptr<mettagrid::Handler>>> handlers) {
  _on_tag_remove = std::move(handlers);
}

bool GridObject::has_on_use_handler() const {
  return _on_use_handler != nullptr;
}

const std::vector<mettagrid::AOEConfig>& GridObject::aoe_configs() const {
  return _aoe_configs;
}

bool GridObject::onUse(Agent& actor, ActionArg /*arg*/) {
  if (!_on_use_handler) {
    return false;
  }
  mettagrid::HandlerContext ctx(&actor, this, nullptr, _tag_index);
  ctx.grid = _grid;
  return _on_use_handler->try_apply(ctx);
}

bool GridObject::has_tag(int tag_id) const {
  if (tag_id < 0 || static_cast<size_t>(tag_id) >= kMaxTags) return false;
  return tag_bits.test(tag_id);
}

void GridObject::add_tag(int tag_id) {
  if (tag_id < 0 || static_cast<size_t>(tag_id) >= kMaxTags) return;
  if (!tag_bits.test(tag_id)) {
    tag_bits.set(tag_id);
    if (_tag_index != nullptr) {
      _tag_index->on_tag_added(this, tag_id);
    }
  }
}

void GridObject::remove_tag(int tag_id) {
  if (tag_id < 0 || static_cast<size_t>(tag_id) >= kMaxTags) return;
  if (tag_bits.test(tag_id)) {
    tag_bits.reset(tag_id);
    if (_tag_index != nullptr) {
      _tag_index->on_tag_removed(this, tag_id);
    }
  }
}

// Build a handler context for tag lifecycle dispatch, propagating all fields from the outer context
static mettagrid::HandlerContext make_tag_handler_ctx(GridObject* obj, const mettagrid::HandlerContext& ctx) {
  mettagrid::HandlerContext handler_ctx;
  handler_ctx.actor = obj;
  handler_ctx.target = obj;
  handler_ctx.game_stats = ctx.game_stats;
  handler_ctx.tag_index = ctx.tag_index;
  handler_ctx.grid = ctx.grid;
  handler_ctx.collectives = ctx.collectives;
  handler_ctx.query_system = ctx.query_system;
  handler_ctx.skip_on_update_trigger = false;
  return handler_ctx;
}

void GridObject::add_tag(int tag_id, const mettagrid::HandlerContext& ctx) {
  if (tag_id < 0 || static_cast<size_t>(tag_id) >= kMaxTags) return;
  if (tag_bits.test(tag_id)) return;  // already present
  tag_bits.set(tag_id);
  if (ctx.tag_index != nullptr) {
    ctx.tag_index->on_tag_added(this, tag_id);
    if (!ctx.skip_on_update_trigger) {
      auto it = _on_tag_add.find(tag_id);
      if (it != _on_tag_add.end()) {
        auto handler_ctx = make_tag_handler_ctx(this, ctx);
        for (auto& handler : it->second) {
          handler->try_apply(handler_ctx);
        }
      }
    }
  }
}

void GridObject::remove_tag(int tag_id, const mettagrid::HandlerContext& ctx) {
  if (tag_id < 0 || static_cast<size_t>(tag_id) >= kMaxTags) return;
  if (!tag_bits.test(tag_id)) return;  // not present
  tag_bits.reset(tag_id);
  if (ctx.tag_index != nullptr) {
    ctx.tag_index->on_tag_removed(this, tag_id);
    if (!ctx.skip_on_update_trigger) {
      auto it = _on_tag_remove.find(tag_id);
      if (it != _on_tag_remove.end()) {
        auto handler_ctx = make_tag_handler_ctx(this, ctx);
        for (auto& handler : it->second) {
          handler->try_apply(handler_ctx);
        }
      }
    }
  }
}

void GridObject::apply_on_tag_add_handlers(int tag_id, const mettagrid::HandlerContext& ctx) {
  auto it = _on_tag_add.find(tag_id);
  if (it != _on_tag_add.end() && ctx.tag_index != nullptr) {
    auto handler_ctx = make_tag_handler_ctx(this, ctx);
    for (auto& handler : it->second) {
      handler->try_apply(handler_ctx);
    }
  }
}

void GridObject::apply_on_tag_remove_handlers(int tag_id, const mettagrid::HandlerContext& ctx) {
  auto it = _on_tag_remove.find(tag_id);
  if (it != _on_tag_remove.end() && ctx.tag_index != nullptr) {
    auto handler_ctx = make_tag_handler_ctx(this, ctx);
    for (auto& handler : it->second) {
      handler->try_apply(handler_ctx);
    }
  }
}

std::vector<PartialObservationToken> GridObject::obs_features() const {
  std::vector<PartialObservationToken> features;
  features.reserve(tag_bits.count() + 3 +
                   (obs_encoder ? inventory.get().size() * obs_encoder->get_num_inventory_tokens() : 0));

  // Emit collective ID if this object belongs to a collective and the feature is configured
  Collective* collective = getCollective();
  if (collective != nullptr && ObservationFeature::Collective != 0) {
    features.push_back({ObservationFeature::Collective, static_cast<ObservationType>(collective->id)});
  }

  // Emit tag features
  for (size_t i = 0; i < kMaxTags; ++i) {
    if (tag_bits.test(i)) {
      features.push_back({ObservationFeature::Tag, static_cast<ObservationType>(i)});
    }
  }

  // Emit vibe if non-zero
  if (vibe != 0) {
    features.push_back({ObservationFeature::Vibe, static_cast<ObservationType>(vibe)});
  }

  // Emit inventory using multi-token encoding (if obs_encoder is available)
  if (obs_encoder) {
    for (const auto& [item, amount] : inventory.get()) {
      assert(amount > 0);
      obs_encoder->append_inventory_tokens(features, item, amount);
    }
  }

  return features;
}

size_t GridObject::max_obs_features(size_t max_tags, size_t num_resources, size_t tokens_per_item) {
  // 1 (collective) + max_tags + 1 (vibe) + (num_resources * tokens_per_item)
  return 1 + max_tags + 1 + (num_resources * tokens_per_item);
}

size_t GridObject::write_obs_features(PartialObservationToken* out, size_t max_tokens) const {
  size_t written = 0;

  // Emit collective ID if this object belongs to a collective and the feature is configured
  Collective* collective = getCollective();
  if (collective != nullptr && ObservationFeature::Collective != 0) {
    if (written < max_tokens) {
      out[written++] = {ObservationFeature::Collective, static_cast<ObservationType>(collective->id)};
    }
  }

  // Emit tag features
  for (size_t i = 0; i < kMaxTags && written < max_tokens; ++i) {
    if (tag_bits.test(i)) {
      out[written++] = {ObservationFeature::Tag, static_cast<ObservationType>(i)};
    }
  }

  // Emit vibe if non-zero
  if (vibe != 0 && written < max_tokens) {
    out[written++] = {ObservationFeature::Vibe, static_cast<ObservationType>(vibe)};
  }

  // Emit inventory using multi-token encoding (if obs_encoder is available)
  if (obs_encoder) {
    for (const auto& [item, amount] : inventory.items()) {
      if (written >= max_tokens) break;
      assert(amount > 0);
      written += obs_encoder->write_inventory_tokens(out + written, max_tokens - written, item, amount);
    }
  }

  return written;
}
