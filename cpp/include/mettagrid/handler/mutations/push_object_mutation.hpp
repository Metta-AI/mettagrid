#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_PUSH_OBJECT_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_PUSH_OBJECT_MUTATION_HPP_

#include <algorithm>

#include "core/grid_object.hpp"
#include "core/mutation_config.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation.hpp"

namespace mettagrid {

/**
 * PushObjectMutation: push ctx.target one cell further along the
 * actor->target direction. Fails (ctx.mutation_failed = true) if the
 * destination is off-grid or occupied.
 *
 * The direction vector (target - actor) is clamped independently on
 * each axis to [-1, 1], so:
 *   - Cardinal adjacency -> 1-cell cardinal push (the usual kick).
 *   - Diagonal adjacency -> 1-cell diagonal push.
 *   - Non-adjacent (|dr|>1 or |dc|>1) -> still a unit step in the
 *     direction's sign, not a proportional push. Keeps the primitive
 *     well-behaved when wired into handlers where actor and target may
 *     not be strictly adjacent.
 *   - Same cell (dr==0 and dc==0) -> dest equals target's own cell, so
 *     is_empty fails and the mutation fails. Degenerate but safe.
 */
class PushObjectMutation : public Mutation {
public:
  explicit PushObjectMutation(const PushObjectMutationConfig& /*config*/) {}

  void apply(HandlerContext& ctx) override {
    if (!ctx.grid || !ctx.actor || !ctx.target) {
      ctx.mutation_failed = true;
      return;
    }

    const GridLocation& a = ctx.actor->location;
    const GridLocation& t = ctx.target->location;

    // Direction from actor to target. Use signed arithmetic to avoid
    // uint16_t underflow when actor is south/east of target. Clamp each
    // axis to [-1, 1] so the push is always a unit step (cardinal or
    // diagonal) regardless of how far the actor is from the target.
    int raw_dr = static_cast<int>(t.r) - static_cast<int>(a.r);
    int raw_dc = static_cast<int>(t.c) - static_cast<int>(a.c);
    int dr = std::clamp(raw_dr, -1, 1);
    int dc = std::clamp(raw_dc, -1, 1);

    int new_r = static_cast<int>(t.r) + dr;
    int new_c = static_cast<int>(t.c) + dc;

    if (new_r < 0 || new_c < 0 || new_r >= static_cast<int>(ctx.grid->height) ||
        new_c >= static_cast<int>(ctx.grid->width)) {
      ctx.mutation_failed = true;
      return;
    }

    GridLocation dest(static_cast<GridCoord>(new_r), static_cast<GridCoord>(new_c));
    if (!ctx.grid->is_empty(dest.r, dest.c)) {
      ctx.mutation_failed = true;
      return;
    }

    if (!ctx.grid->move_object(*ctx.target, dest)) {
      ctx.mutation_failed = true;
      return;
    }
  }
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_PUSH_OBJECT_MUTATION_HPP_
