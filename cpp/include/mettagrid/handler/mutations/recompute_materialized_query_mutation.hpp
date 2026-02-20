#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_RECOMPUTE_MATERIALIZED_QUERY_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_RECOMPUTE_MATERIALIZED_QUERY_MUTATION_HPP_

#include <cassert>

#include "core/query_system.hpp"
#include "handler/handler_config.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation.hpp"

namespace mettagrid {

/**
 * RecomputeMaterializedQueryMutation: Trigger recomputation of a MaterializedQuery tag.
 */
class RecomputeMaterializedQueryMutation : public Mutation {
public:
  explicit RecomputeMaterializedQueryMutation(const RecomputeMaterializedQueryMutationConfig& config)
      : _config(config) {}

  void apply(HandlerContext& ctx) override {
    ctx.query_system->recompute(_config.tag_id, ctx);
  }

private:
  RecomputeMaterializedQueryMutationConfig _config;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_RECOMPUTE_MATERIALIZED_QUERY_MUTATION_HPP_
