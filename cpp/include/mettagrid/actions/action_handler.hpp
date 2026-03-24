// action_handler.hpp
#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_ACTIONS_ACTION_HANDLER_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_ACTIONS_ACTION_HANDLER_HPP_

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <cassert>
#include <string>
#include <unordered_map>
#include <vector>

#include "core/grid.hpp"
#include "core/grid_object.hpp"
#include "core/types.hpp"
#include "handler/handler_context.hpp"
#include "objects/agent.hpp"
#include "objects/constants.hpp"

struct ActionConfig {
  std::unordered_map<InventoryItem, InventoryQuantity> required_resources;
  std::unordered_map<InventoryItem, InventoryQuantity> consumed_resources;

  ActionConfig(const std::unordered_map<InventoryItem, InventoryQuantity>& required_resources = {},
               const std::unordered_map<InventoryItem, InventoryQuantity>& consumed_resources = {})
      : required_resources(required_resources), consumed_resources(consumed_resources) {}

  virtual ~ActionConfig() {}
};

// Forward declaration
class ActionHandler;

// Action represents a specific action variant (e.g., move_north, attack_0, etc.)
class Action {
public:
  Action(ActionHandler* handler, const std::string& name, ActionArg arg) : _handler(handler), _name(name), _arg(arg) {}

  bool handle(Agent& actor, const mettagrid::HandlerContext& ctx);

  std::string name() const {
    return _name;
  }

  ActionArg arg() const {
    return _arg;
  }

  ActionHandler* handler() const {
    return _handler;
  }

private:
  ActionHandler* _handler;
  std::string _name;
  ActionArg _arg;
};

class ActionHandler {
public:
  unsigned char priority;

  ActionHandler(const ActionConfig& cfg, const std::string& action_name) : priority(0), _action_name(action_name) {
    (void)cfg;
  }

  virtual ~ActionHandler() {}

  void init() {
    // Create actions after construction, when the derived class vtable is set up
    if (_actions.empty()) {
      _actions = create_actions();
    }
  }

  // Returns true if the action was executed, false otherwise. In particular, a result of false should have no impact
  // on the environment, and should imply that the agent effectively took a noop action.
  bool handle_action(Agent& actor, ActionArg arg, const mettagrid::HandlerContext& ctx) {
    actor.last_animation_id = kNoAnimation;
    bool success = _handle_action(actor, arg, ctx);

    // The intention here is to provide a metric that reports when an agent has stayed in one location for a long
    // period, perhaps spinning in circles. We think this could be a good indicator that a policy has collapsed.
    if (actor.location == actor.prev_location) {
      actor.steps_without_motion += 1;
      if (actor.steps_without_motion > actor.stats.get("status.max_steps_without_motion")) {
        actor.stats.set("status.max_steps_without_motion", actor.steps_without_motion);
      }
    } else {
      actor.steps_without_motion = 0;
    }

    // Update tracking for this agent
    actor.prev_location = actor.location;

    // Track success/failure
    if (success) {
      actor.stats.incr("action." + _action_name + ".success");
    } else {
      actor.stats.incr("action." + _action_name + ".failed");
      actor.stats.incr("action.failed");
    }

    return success;
  }

  std::string action_name() const {
    return _action_name;
  }

  virtual std::string variant_name(ActionArg arg) const {
    return _action_name + "_" + std::to_string(static_cast<int>(arg));
  }

  // Get the actions for this handler
  const std::vector<Action>& actions() const {
    return _actions;
  }

protected:
  // Subclasses override this to create their specific action instances
  virtual std::vector<Action> create_actions() = 0;

  virtual bool _handle_action(Agent& actor, ActionArg arg, const mettagrid::HandlerContext& ctx) = 0;

  std::string _action_name;
  std::vector<Action> _actions;
};

// Implement Action::handle() inline after ActionHandler is fully defined
inline bool Action::handle(Agent& actor, const mettagrid::HandlerContext& ctx) {
  return _handler->handle_action(actor, _arg, ctx);
}

namespace py = pybind11;

inline void bind_action_config(py::module& m) {
  py::class_<ActionConfig, std::shared_ptr<ActionConfig>>(m, "ActionConfig")
      .def(py::init<const std::unordered_map<InventoryItem, InventoryQuantity>&,
                    const std::unordered_map<InventoryItem, InventoryQuantity>&>(),
           py::arg("required_resources") = std::unordered_map<InventoryItem, InventoryQuantity>(),
           py::arg("consumed_resources") = std::unordered_map<InventoryItem, InventoryQuantity>())
      .def_readwrite("required_resources", &ActionConfig::required_resources)
      .def_readwrite("consumed_resources", &ActionConfig::consumed_resources);
}

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_ACTIONS_ACTION_HANDLER_HPP_
