#include "core/grid_object.hpp"

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
  this->tag_ids = tags;
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
  // Try each on_use handler in order until one succeeds
  for (auto& handler : _on_use_handlers) {
    if (handler->try_apply(&actor, this)) {
      return true;
    }
  }
  return false;
}

void GridObject::fire_on_update_handlers() {
  // Prevent all recursion
  mettagrid::HandlerContext ctx(nullptr, this, /*skip_on_update_trigger=*/true);

  // Try each on_update handler - all that pass filters will be applied
  for (auto& handler : _on_update_handlers) {
    handler->try_apply(ctx);
  }
}
