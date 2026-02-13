#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_RECOMPUTE_QUERY_TAG_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_RECOMPUTE_QUERY_TAG_MUTATION_HPP_

#include "core/query_system.hpp"
#include "handler/handler_config.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation.hpp"

namespace mettagrid {

/**
 * RecomputeQueryTagMutation: Trigger recomputation of a QueryTag.
 */
class RecomputeQueryTagMutation : public Mutation {
public:
  explicit RecomputeQueryTagMutation(const RecomputeQueryTagMutationConfig& config) : _config(config) {}

  void apply(HandlerContext& ctx) override {
    if (ctx.query_system != nullptr) {
      ctx.query_system->recompute(_config.tag_id);
    }
  }

private:
  RecomputeQueryTagMutationConfig _config;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_RECOMPUTE_QUERY_TAG_MUTATION_HPP_
