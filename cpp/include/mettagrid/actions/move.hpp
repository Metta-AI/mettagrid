#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_ACTIONS_MOVE_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_ACTIONS_MOVE_HPP_

#include <cassert>
#include <string>
#include <unordered_map>
#include <utility>
#include <variant>
#include <vector>

#include "actions/action_handler.hpp"
#include "actions/move_config.hpp"
#include "actions/orientation.hpp"
#include "core/filter_config.hpp"
#include "core/grid_object.hpp"
#include "core/types.hpp"
#include "handler/handler.hpp"
#include "handler/handler_config.hpp"
#include "handler/handler_context.hpp"
#include "objects/agent.hpp"
#include "objects/constants.hpp"
#include "objects/usable.hpp"

struct GameConfig;

struct MoveHandler {
  mettagrid::Handler handler;
  unsigned int max_range = 1;
  bool accepts_empty = false;

  explicit MoveHandler(const mettagrid::HandlerConfig& cfg) : handler(cfg) {
    for (const auto& filter : cfg.filters) {
      if (auto* mdf = std::get_if<mettagrid::MaxDistanceFilterConfig>(&filter)) {
        max_range = mdf->radius > 0 ? mdf->radius : 1;
      }
      if (std::holds_alternative<mettagrid::TargetLocEmptyFilterConfig>(filter)) {
        accepts_empty = true;
      }
    }
  }

  MoveHandler(MoveHandler&&) = default;
  MoveHandler& operator=(MoveHandler&&) = default;
  MoveHandler(const MoveHandler&) = delete;
  MoveHandler& operator=(const MoveHandler&) = delete;
};

class Move : public ActionHandler {
public:
  explicit Move(const MoveActionConfig& cfg, [[maybe_unused]] const GameConfig* game_config)
      : ActionHandler(cfg, "move"), _allowed_directions(cfg.allowed_directions) {
    // Build direction name to orientation mapping
    _direction_map["north"] = Orientation::North;
    _direction_map["south"] = Orientation::South;
    _direction_map["west"] = Orientation::West;
    _direction_map["east"] = Orientation::East;
    _direction_map["northwest"] = Orientation::Northwest;
    _direction_map["northeast"] = Orientation::Northeast;
    _direction_map["southwest"] = Orientation::Southwest;
    _direction_map["southeast"] = Orientation::Southeast;

    // Build move handlers from config
    for (const auto& handler_cfg : cfg.handlers) {
      _move_handlers.emplace_back(handler_cfg);
    }
  }

  std::vector<Action> create_actions() override {
    std::vector<Action> actions;
    // Create actions in the order specified by the config
    for (const std::string& direction : _allowed_directions) {
      auto it = _direction_map.find(direction);
      if (it != _direction_map.end()) {
        actions.emplace_back(this, "move_" + direction, static_cast<ActionArg>(it->second));
      }
    }
    return actions;
  }

protected:
  bool _handle_action(Agent& actor, ActionArg arg, const mettagrid::HandlerContext& ctx) override {
    Orientation move_direction = static_cast<Orientation>(arg);
    int dc, dr;
    getOrientationDelta(move_direction, dc, dr);

    for (auto& mh : _move_handlers) {
      // Line-scan in direction up to this handler's range
      for (unsigned int i = 1; i <= mh.max_range; i++) {
        GridLocation target_loc = actor.location;
        target_loc.r = static_cast<GridCoord>(static_cast<int>(target_loc.r) + dr * static_cast<int>(i));
        target_loc.c = static_cast<GridCoord>(static_cast<int>(target_loc.c) + dc * static_cast<int>(i));

        if (!ctx.grid->is_valid_location(target_loc)) break;

        GridObject* target_obj = ctx.grid->object_at(target_loc);

        bool cell_is_empty = (target_obj == nullptr);
        if (cell_is_empty && !mh.accepts_empty) continue;  // scan past empty cells

        // Build context for this handler
        mettagrid::HandlerContext move_ctx = ctx;
        move_ctx.actor = &actor;
        move_ctx.target = target_obj;
        move_ctx.target_location = target_loc;
        move_ctx.distance = i;
        move_ctx.move_direction = arg;

        if (mh.handler.try_apply(move_ctx)) {
          return true;
        }
        break;  // Found something but handler didn't match — stop for this handler
      }
    }
    return false;
  }

  std::string variant_name(ActionArg arg) const override {
    Orientation move_direction = static_cast<Orientation>(arg);
    return std::string(action_name()) + "_" + OrientationFullNames[static_cast<size_t>(move_direction)];
  }

private:
  std::vector<std::string> _allowed_directions;
  std::unordered_map<std::string, Orientation> _direction_map;
  std::vector<MoveHandler> _move_handlers;
};

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_ACTIONS_MOVE_HPP_
