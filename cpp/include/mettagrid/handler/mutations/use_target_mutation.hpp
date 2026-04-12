#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_USE_TARGET_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_USE_TARGET_MUTATION_HPP_

#include "core/mutation_config.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation.hpp"
#include "objects/agent.hpp"
#include "objects/constants.hpp"
#include "objects/usable.hpp"

namespace mettagrid {

class UseTargetMutation : public Mutation {
public:
  explicit UseTargetMutation(const UseTargetMutationConfig& /*config*/) {}

  void apply(HandlerContext& ctx) override {
    auto* usable = dynamic_cast<Usable*>(ctx.target);
    auto* actor = dynamic_cast<Agent*>(ctx.actor);
    if (!usable || !actor) {
      ctx.mutation_failed = true;
      return;
    }
    if (!usable->onUse(*actor, ctx.move_direction, ctx)) {
      ctx.mutation_failed = true;
      return;
    }
    actor->apply_on_after_use(ctx);
    actor->last_animation_id = kBumpAnimation;
  }
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_USE_TARGET_MUTATION_HPP_
