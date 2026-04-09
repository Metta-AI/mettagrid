#include "core/query_system.hpp"

#include <algorithm>
#include <cassert>
#include <cstdlib>
#include <limits>
#include <queue>
#include <random>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "core/grid.hpp"
#include "core/grid_object.hpp"
#include "core/tag_index.hpp"
#include "handler/filters/filter.hpp"
#include "handler/filters/filter_factory.hpp"
#include "handler/handler_context.hpp"

namespace mettagrid {

QuerySystem::QuerySystem(const std::vector<MaterializedQueryTag>& configs) {
  _query_tags.reserve(configs.size());

  for (const auto& cfg : configs) {
    QueryTagDef def;
    def.tag_id = cfg.tag_id;
    def.query = cfg.query;
    _query_tags.push_back(std::move(def));
  }
}

bool QuerySystem::matches_filters(GridObject* obj,
                                  const std::vector<FilterConfig>& filter_configs,
                                  const HandlerContext& ctx) {
  if (filter_configs.empty()) {
    return true;
  }

  HandlerContext filter_ctx = ctx;
  filter_ctx.target = obj;

  for (const auto& filter_cfg : filter_configs) {
    auto f = create_filter(filter_cfg);
    if (f && !f->passes(filter_ctx)) {
      return false;
    }
  }
  return true;
}

bool QuerySystem::matches_edge_filters(GridObject* bfs_source,
                                       GridObject* candidate,
                                       const std::vector<FilterConfig>& filter_configs,
                                       const HandlerContext& ctx) {
  if (filter_configs.empty()) {
    return true;
  }

  HandlerContext edge_ctx = ctx;
  edge_ctx.source = bfs_source;
  edge_ctx.target = candidate;

  for (const auto& filter_cfg : filter_configs) {
    auto f = create_filter(filter_cfg);
    if (f && !f->passes(edge_ctx)) {
      return false;
    }
  }
  return true;
}

std::vector<GridObject*> QuerySystem::apply_limits(std::vector<GridObject*> results,
                                                   int max_items,
                                                   QueryOrderBy order_by,
                                                   const HandlerContext& ctx) {
  if (order_by == QueryOrderBy::random) {
    std::shuffle(results.begin(), results.end(), *ctx.rng);
  }

  if (max_items >= 0 && static_cast<int>(results.size()) > max_items) {
    results.resize(max_items);
  }

  return results;
}

void QuerySystem::compute_all(const HandlerContext& ctx) {
  _computing = true;
  // Build a context for tag operations (skip handlers during query computation)
  HandlerContext tag_ctx = ctx;
  tag_ctx.skip_on_update_trigger = true;

  for (const auto& def : _query_tags) {
    // Remove existing tag from all objects that have it
    auto tagged_objects = ctx.tag_index->get_objects_with_tag(def.tag_id);
    for (auto* obj : tagged_objects) {
      tag_ctx.actor = obj;
      tag_ctx.target = obj;
      obj->remove_tag(def.tag_id, tag_ctx);
    }

    // Evaluate query and apply tag
    if (def.query) {
      auto result = def.query->evaluate(ctx);
      for (auto* obj : result) {
        tag_ctx.actor = obj;
        tag_ctx.target = obj;
        obj->add_tag(def.tag_id, tag_ctx);
      }
    }
  }
  _computing = false;
}

void QuerySystem::recompute(int tag_id, const HandlerContext& ctx) {
  _computing = true;
  HandlerContext tag_ctx = ctx;
  tag_ctx.skip_on_update_trigger = true;

  std::vector<GridObject*> objects_that_lost_tag;
  std::vector<GridObject*> objects_that_keep_tag;
  std::unordered_set<GridObject*> keep_tag_set;

  for (const auto& def : _query_tags) {
    if (def.tag_id == tag_id) {
      // Remove existing tag from all objects that have it (skip on_tag_remove during recompute)
      auto tagged_objects = ctx.tag_index->get_objects_with_tag(def.tag_id);
      objects_that_lost_tag.assign(tagged_objects.begin(), tagged_objects.end());
      for (auto* obj : tagged_objects) {
        tag_ctx.actor = obj;
        tag_ctx.target = obj;
        obj->remove_tag(def.tag_id, tag_ctx);
      }

      // Evaluate query and apply tag
      if (def.query) {
        auto result = def.query->evaluate(ctx);
        for (auto* obj : result) {
          if (keep_tag_set.insert(obj).second) {
            objects_that_keep_tag.push_back(obj);
          }
          tag_ctx.actor = obj;
          tag_ctx.target = obj;
          obj->add_tag(def.tag_id, tag_ctx);
        }
      }
      break;
    }
  }
  _computing = false;

  // Fire on_tag_remove for objects that lost the tag and did NOT get it back
  tag_ctx.skip_on_update_trigger = false;
  std::unordered_set<GridObject*> original_set(objects_that_lost_tag.begin(), objects_that_lost_tag.end());
  for (auto* obj : objects_that_lost_tag) {
    if (keep_tag_set.count(obj) == 0) {
      tag_ctx.actor = obj;
      tag_ctx.target = obj;
      obj->apply_on_tag_remove_handlers(tag_id, tag_ctx);
    }
  }

  // Fire on_tag_add for objects that newly gained the tag
  for (auto* obj : objects_that_keep_tag) {
    if (original_set.count(obj) == 0) {
      tag_ctx.actor = obj;
      tag_ctx.target = obj;
      obj->apply_on_tag_add_handlers(tag_id, tag_ctx);
    }
  }
}

// TagQueryConfig::evaluate - find objects with tag, apply filters and limits
std::vector<GridObject*> TagQueryConfig::evaluate(const HandlerContext& ctx) const {
  std::vector<GridObject*> result;
  const auto& candidates = ctx.tag_index->get_objects_with_tag(tag_id);
  for (auto* obj : candidates) {
    if (QuerySystem::matches_filters(obj, filters, ctx)) {
      result.push_back(obj);
    }
  }
  return QuerySystem::apply_limits(std::move(result), max_items, order_by, ctx);
}

// ClosureQueryConfig::evaluate - BFS from source through candidates.
// Edge filters are binary: evaluated with source=net_member, target=candidate.
std::vector<GridObject*> ClosureQueryConfig::evaluate(const HandlerContext& ctx) const {
  assert(source && "ClosureQueryConfig requires a non-null source query");

  auto roots = source->evaluate(ctx);

  if (!candidates) {
    return QuerySystem::apply_limits(std::move(roots), max_items, order_by, ctx);
  }

  auto candidate_pool = candidates->evaluate(ctx);
  std::unordered_set<GridObject*> visited;
  std::queue<GridObject*> frontier;
  std::vector<GridObject*> result;
  result.reserve(roots.size() + candidate_pool.size());

  for (auto* obj : roots) {
    if (visited.insert(obj).second) {
      frontier.push(obj);
      result.push_back(obj);
    }
  }

  while (!frontier.empty()) {
    GridObject* current = frontier.front();
    frontier.pop();

    for (auto* candidate : candidate_pool) {
      if (visited.count(candidate)) continue;

      if (!QuerySystem::matches_edge_filters(current, candidate, edge_filters, ctx)) continue;

      visited.insert(candidate);
      frontier.push(candidate);
      result.push_back(candidate);
    }
  }

  if (!result_filters.empty()) {
    std::vector<GridObject*> filtered;
    for (auto* obj : result) {
      if (QuerySystem::matches_filters(obj, result_filters, ctx)) {
        filtered.push_back(obj);
      }
    }
    result = std::move(filtered);
  }

  return QuerySystem::apply_limits(std::move(result), max_items, order_by, ctx);
}

// FilteredQueryConfig::evaluate - evaluate inner query, filter results, apply limits
std::vector<GridObject*> FilteredQueryConfig::evaluate(const HandlerContext& ctx) const {
  assert(source && "FilteredQueryConfig requires a non-null source query");

  auto candidates = source->evaluate(ctx);

  std::vector<GridObject*> result;
  result.reserve(candidates.size());
  for (auto* obj : candidates) {
    if (QuerySystem::matches_filters(obj, filters, ctx)) {
      result.push_back(obj);
    }
  }

  return QuerySystem::apply_limits(std::move(result), max_items, order_by, ctx);
}

// RaycastQueryConfig::evaluate - walk rays from source objects, collect hits
std::vector<GridObject*> RaycastQueryConfig::evaluate(const HandlerContext& ctx) const {
  assert(source && "RaycastQueryConfig requires a non-null source query");
  assert(ctx.grid && "RaycastQueryConfig requires grid in HandlerContext");

  auto sources = source->evaluate(ctx);

  // Default to 4 cardinal directions if none specified.
  static const std::vector<std::pair<int, int>> CARDINALS = {{-1, 0}, {1, 0}, {0, 1}, {0, -1}};
  const auto& dirs = directions.empty() ? CARDINALS : directions;

  std::vector<GridObject*> result;
  std::unordered_set<GridObject*> seen;  // deduplicate across multiple sources/arms

  for (auto* src : sources) {
    for (const auto& dir : dirs) {
      for (unsigned int dist = 1; dist <= max_range; ++dist) {
        int64_t r = static_cast<int64_t>(src->location.r) + static_cast<int64_t>(dir.first) * dist;
        int64_t c = static_cast<int64_t>(src->location.c) + static_cast<int64_t>(dir.second) * dist;

        if (r < 0 || c < 0 || r >= static_cast<int64_t>(ctx.grid->height) ||
            c >= static_cast<int64_t>(ctx.grid->width)) {
          break;
        }

        GridLocation loc(static_cast<GridCoord>(r), static_cast<GridCoord>(c));
        GridObject* obj = ctx.grid->object_at(loc);

        if (obj == nullptr) {
          continue;  // empty cell, ray continues
        }

        // Check if this object blocks the ray (matches ANY blocker filter).
        // Uses OR semantics: a wall matches isA("wall"), a crate matches
        // isA("crate"), and either one blocks the ray.
        bool is_blocker = false;
        if (!blocker.empty()) {
          HandlerContext blocker_ctx = ctx;
          blocker_ctx.target = obj;
          for (const auto& blocker_cfg : blocker) {
            auto f = create_filter(blocker_cfg);
            if (f && f->passes(blocker_ctx)) {
              is_blocker = true;
              break;
            }
          }
        }

        if (is_blocker) {
          if (include_blocker && seen.insert(obj).second) {
            result.push_back(obj);
          }
          break;  // ray stops at blocker
        }

        // Non-blocking object on the ray — include it
        if (seen.insert(obj).second) {
          result.push_back(obj);
        }
      }
    }
  }

  return QuerySystem::apply_limits(std::move(result), max_items, order_by, ctx);
}

}  // namespace mettagrid
