#include "handler/mutations/spawn_object_mutation.hpp"

#include "config/mettagrid_config.hpp"
#include "core/aoe_tracker.hpp"
#include "core/grid_object_factory.hpp"
#include "handler/handler_context.hpp"

namespace mettagrid {

void SpawnObjectMutation::apply(HandlerContext& ctx) {
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

  // Update ctx.target to the spawned object so subsequent mutations in
  // the same handler can reference it (e.g. deposit resources onto it).
  ctx.target = obj;

  if (ctx.tag_index) {
    ctx.tag_index->register_object(obj);
  }

  // Queue AOE registration for the spawned object. Uses deferred_register to
  // avoid mutating AOETracker containers during an active apply_fixed/apply_mobile
  // traversal (if this mutation is triggered by an AOE handler).
  if (ctx.aoe_tracker) {
    for (const auto& aoe_config : obj->aoe_configs()) {
      ctx.aoe_tracker->deferred_register(*obj, aoe_config);
    }
  }
}

}  // namespace mettagrid
