#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_SET_RELATIVE_TARGET_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_SET_RELATIVE_TARGET_MUTATION_HPP_

#include <stdexcept>
#include <string>

#include "actions/orientation.hpp"
#include "core/grid.hpp"
#include "core/grid_object.hpp"
#include "core/mutation_config.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation.hpp"

namespace mettagrid {

/**
 * SetRelativeTargetMutation: compute ctx.target_location as
 * actor.location + direction * distance, and refresh ctx.target to the
 * object at that cell (or nullptr). Also updates ctx.move_direction so
 * downstream mutations (e.g. PushObjectMutation) see a consistent
 * move direction even when the handler did not originate from a move
 * action (events, AOEs, onUse, ...).
 *
 * Sets ctx.mutation_failed = true if ctx.actor is null or the computed
 * cell is off-grid; the grid and per-cell state are left unchanged.
 */
class SetRelativeTargetMutation : public Mutation {
public:
  explicit SetRelativeTargetMutation(const SetRelativeTargetMutationConfig& config)
      : direction_(static_cast<Orientation>(config.direction)), distance_(config.distance) {
    // getOrientationDelta indexes fixed-size tables of length 8; reject anything
    // that could land out of bounds before we ever dereference those tables.
    if (config.direction < 0 || config.direction > 7) {
      throw std::runtime_error("SetRelativeTargetMutationConfig::direction must be in [0, 7], got " +
                               std::to_string(config.direction));
    }
  }

  void apply(HandlerContext& ctx) override {
    if (!ctx.grid || !ctx.actor) {
      ctx.mutation_failed = true;
      return;
    }

    int dx = 0, dy = 0;
    getOrientationDelta(direction_, dx, dy);
    const int step = static_cast<int>(distance_);
    const int new_r = static_cast<int>(ctx.actor->location.r) + dy * step;
    const int new_c = static_cast<int>(ctx.actor->location.c) + dx * step;

    if (new_r < 0 || new_c < 0 || new_r >= static_cast<int>(ctx.grid->height) ||
        new_c >= static_cast<int>(ctx.grid->width)) {
      ctx.mutation_failed = true;
      return;
    }

    GridLocation loc(static_cast<GridCoord>(new_r), static_cast<GridCoord>(new_c));
    ctx.target_location = loc;
    ctx.target = ctx.grid->object_at(loc);
    ctx.move_direction = static_cast<ActionArg>(direction_);
    ctx.distance = distance_;
  }

private:
  Orientation direction_;
  unsigned int distance_;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_SET_RELATIVE_TARGET_MUTATION_HPP_
