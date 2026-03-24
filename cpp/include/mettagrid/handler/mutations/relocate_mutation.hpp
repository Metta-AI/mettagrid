#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_RELOCATE_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_RELOCATE_MUTATION_HPP_

#include "core/mutation_config.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation.hpp"
#include "objects/agent.hpp"

namespace mettagrid {

class RelocateMutation : public Mutation {
public:
  explicit RelocateMutation(const RelocateMutationConfig& /*config*/) {}

  void apply(HandlerContext& ctx) override {
    if (!ctx.grid) return;
    auto* agent = dynamic_cast<Agent*>(ctx.actor);
    if (!agent) return;
    ctx.grid->move_object(*agent, ctx.target_location);
  }
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_RELOCATE_MUTATION_HPP_
