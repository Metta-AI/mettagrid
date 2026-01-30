#include "core/grid_object.hpp"

#include <algorithm>
#include <cassert>

#include "config/observation_features.hpp"
#include "core/tag_index.hpp"
#include "handler/handler.hpp"
#include "handler/handler_context.hpp"
#include "objects/agent.hpp"
#include "objects/collective.hpp"
#include "systems/observation_encoder.hpp"

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
  this->tag_ids = std::set<int>(tags.begin(), tags.end());
  this->vibe = object_vibe;
}

void GridObject::set_on_use_handlers(std::vector<std::shared_ptr<mettagrid::Handler>> handlers) {
  _on_use_handlers = std::move(handlers);
}

void GridObject::set_aoe_configs(std::vector<mettagrid::AOEConfig> configs) {
  _aoe_configs = std::move(configs);
}

bool GridObject::has_on_use_handlers() const {
  return !_on_use_handlers.empty();
}

const std::vector<mettagrid::AOEConfig>& GridObject::aoe_configs() const {
  return _aoe_configs;
}

bool GridObject::onUse(Agent& actor, ActionArg /*arg*/) {
  mettagrid::HandlerContext ctx(&actor, this, nullptr, _tag_index);
  ctx.grid = _grid;
  // Try each on_use handler in order until one succeeds
  for (auto& handler : _on_use_handlers) {
    if (handler->try_apply(ctx)) {
      return true;
    }
  }
  return false;
}

bool GridObject::has_tag(int tag_id) const {
  return tag_ids.find(tag_id) != tag_ids.end();
}

void GridObject::add_tag(int tag_id) {
  bool added = tag_ids.insert(tag_id).second;
  if (added && _tag_index != nullptr) {
    _tag_index->on_tag_added(this, tag_id);
  }
}

void GridObject::remove_tag(int tag_id) {
  size_t removed = tag_ids.erase(tag_id);
  if (removed > 0 && _tag_index != nullptr) {
    _tag_index->on_tag_removed(this, tag_id);
  }
}

std::vector<PartialObservationToken> GridObject::obs_features() const {
  std::vector<PartialObservationToken> features;
  features.reserve(tag_ids.size() + 3 +
                   (obs_encoder ? inventory.get().size() * obs_encoder->get_num_inventory_tokens() : 0));

  // Emit collective ID if this object belongs to a collective and the feature is configured
  Collective* collective = getCollective();
  if (collective != nullptr && ObservationFeature::Collective != 0) {
    features.push_back({ObservationFeature::Collective, static_cast<ObservationType>(collective->id)});
  }

  // Emit tag features
  for (int tag_id : tag_ids) {
    features.push_back({ObservationFeature::Tag, static_cast<ObservationType>(tag_id)});
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
