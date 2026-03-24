#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_SPAWN_OBJECT_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_SPAWN_OBJECT_MUTATION_HPP_

#include "config/mettagrid_config.hpp"
#include "core/grid_object_factory.hpp"
#include "core/mutation_config.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation.hpp"

namespace mettagrid {

class SpawnObjectMutation : public Mutation {
public:
  explicit SpawnObjectMutation(const SpawnObjectMutationConfig& config) : _object_type(config.object_type) {}

  void apply(HandlerContext& ctx) override {
    if (!ctx.grid || !ctx.game_config) {
      ctx.mutation_failed = true;
      return;
    }

    auto it = ctx.game_config->objects.find(_object_type);
    if (it == ctx.game_config->objects.end()) {
      ctx.mutation_failed = true;
      return;
    }

    if (!ctx.grid->is_empty(ctx.target_location.r, ctx.target_location.c)) {
      ctx.mutation_failed = true;
      return;
    }

    auto* obj = create_object_from_config(ctx.target_location.r,
                                          ctx.target_location.c,
                                          it->second.get(),
                                          ctx.game_stats,
                                          &ctx.game_config->resource_names,
                                          ctx.grid,
                                          nullptr,
                                          nullptr,
                                          ctx.tag_index);
    if (!obj) {
      ctx.mutation_failed = true;
      return;
    }

    bool added = ctx.grid->add_object(obj);
    if (!added) {
      delete obj;
      ctx.mutation_failed = true;
      return;
    }

    if (ctx.tag_index) {
      ctx.tag_index->register_object(obj);
    }
  }

private:
  std::string _object_type;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_SPAWN_OBJECT_MUTATION_HPP_
