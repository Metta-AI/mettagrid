#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_SWAP_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_SWAP_MUTATION_HPP_

#include "core/mutation_config.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation.hpp"
#include "objects/agent.hpp"

namespace mettagrid {

class SwapMutation : public Mutation {
public:
  explicit SwapMutation(const SwapMutationConfig& /*config*/) {}

  void apply(HandlerContext& ctx) override {
    if (!ctx.grid) return;
    auto* actor_agent = dynamic_cast<Agent*>(ctx.actor);
    auto* target_agent = dynamic_cast<Agent*>(ctx.target);
    if (!actor_agent || !target_agent) return;
    ctx.grid->swap_objects(*actor_agent, *target_agent);
    actor_agent->stats.incr("actions.swap");
  }
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_SWAP_MUTATION_HPP_
