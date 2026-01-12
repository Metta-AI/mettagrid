#include "core/grid_object.hpp"

#include "handler/handler.hpp"
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

void GridObject::set_handlers(std::vector<std::shared_ptr<mettagrid::Handler>> handlers) {
  _handlers = std::move(handlers);
}

bool GridObject::has_handlers() const {
  return !_handlers.empty();
}

bool GridObject::onUse(Agent& actor, ActionArg /*arg*/) {
  // Try each handler in order until one succeeds
  for (auto& handler : _handlers) {
    if (handler->try_apply(&actor, this)) {
      return true;
    }
  }
  return false;
}
