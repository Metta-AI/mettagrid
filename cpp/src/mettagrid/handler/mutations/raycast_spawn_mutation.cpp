#include "handler/mutations/raycast_spawn_mutation.hpp"

#include "config/mettagrid_config.hpp"
#include "core/aoe_tracker.hpp"
#include "core/grid.hpp"
#include "core/grid_object.hpp"
#include "core/grid_object_factory.hpp"
#include "core/query_system.hpp"
#include "handler/filters/filter_factory.hpp"
#include "handler/handler_context.hpp"

namespace mettagrid {

void RaycastSpawnMutation::apply(HandlerContext& ctx) {
  if (!ctx.grid || !ctx.game_config || !ctx.target) {
    ctx.mutation_failed = true;
    return;
  }

  auto obj_it = ctx.game_config->objects.find(_config.object_type);
  if (obj_it == ctx.game_config->objects.end()) {
    ctx.mutation_failed = true;
    return;
  }

  const GridLocation& origin = ctx.target->location;

  for (const auto& dir : _config.directions) {
    for (unsigned int dist = 1; dist <= _config.max_range; ++dist) {
      int64_t r = static_cast<int64_t>(origin.r) + static_cast<int64_t>(dir.first) * dist;
      int64_t c = static_cast<int64_t>(origin.c) + static_cast<int64_t>(dir.second) * dist;

      if (r < 0 || c < 0 || r >= static_cast<int64_t>(ctx.grid->height) || c >= static_cast<int64_t>(ctx.grid->width)) {
        break;
      }

      GridLocation loc(static_cast<GridCoord>(r), static_cast<GridCoord>(c));
      GridObject* existing = ctx.grid->object_at(loc);

      if (existing != nullptr) {
        // Cell occupied — check if it's a blocker (ANY filter match = blocked).
        bool is_blocker = false;
        if (!_config.blocker.empty()) {
          HandlerContext blocker_ctx = ctx;
          blocker_ctx.target = existing;
          for (const auto& blocker_cfg : _config.blocker) {
            auto f = create_filter(blocker_cfg);
            if (f && f->passes(blocker_ctx)) {
              is_blocker = true;
              break;
            }
          }
        }
        if (is_blocker) {
          break;  // Blocker stops the ray
        }
        // Non-blocking object — skip cell but continue ray
        continue;
      }

      // Empty cell — spawn the object
      auto* spawned = create_object_from_config(loc.r,
                                                loc.c,
                                                obj_it->second.get(),
                                                ctx.game_stats,
                                                &ctx.game_config->resource_names,
                                                ctx.grid,
                                                nullptr,
                                                nullptr,
                                                ctx.tag_index);
      if (spawned && ctx.grid->add_object(spawned)) {
        if (ctx.tag_index) {
          ctx.tag_index->register_object(spawned);
        }
        if (ctx.aoe_tracker) {
          for (const auto& aoe_cfg : spawned->aoe_configs()) {
            ctx.aoe_tracker->deferred_register(*spawned, aoe_cfg);
          }
        }
      }
    }
  }
}

}  // namespace mettagrid
