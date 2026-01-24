#include "core/grid_object.hpp"

#include "core/tag_index.hpp"
#include "handler/handler.hpp"
#include "handler/handler_context.hpp"
#include "objects/agent.hpp"

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

void GridObject::set_on_update_handlers(std::vector<std::shared_ptr<mettagrid::Handler>> handlers) {
  _on_update_handlers = std::move(handlers);
}

void GridObject::set_aoe_handlers(std::vector<std::shared_ptr<mettagrid::Handler>> handlers) {
  _aoe_handlers = std::move(handlers);
}

bool GridObject::has_on_use_handlers() const {
  return !_on_use_handlers.empty();
}

bool GridObject::has_on_update_handlers() const {
  return !_on_update_handlers.empty();
}

const std::vector<std::shared_ptr<mettagrid::Handler>>& GridObject::aoe_handlers() const {
  return _aoe_handlers;
}

bool GridObject::onUse(Agent& actor, ActionArg /*arg*/) {
  mettagrid::HandlerContext ctx(&actor, this, nullptr, _tag_index);
  // Try each on_use handler in order until one succeeds
  for (auto& handler : _on_use_handlers) {
    if (handler->try_apply(ctx)) {
      return true;
    }
  }
  return false;
}

void GridObject::fire_on_update_handlers() {
  // Prevent all recursion
  mettagrid::HandlerContext ctx(nullptr, this, nullptr, _tag_index, /*skip_on_update_trigger=*/true);

  // Try each on_update handler - all that pass filters will be applied
  for (auto& handler : _on_update_handlers) {
    handler->try_apply(ctx);
  }
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
