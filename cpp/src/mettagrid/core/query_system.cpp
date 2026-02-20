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
  filter_ctx.actor = obj;
  filter_ctx.target = obj;

  for (const auto& filter_cfg : filter_configs) {
    auto f = create_filter(filter_cfg);
    if (f && !f->passes(filter_ctx)) {
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

  if (max_items > 0 && static_cast<int>(results.size()) > max_items) {
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
  std::unordered_set<GridObject*> objects_that_keep_tag;

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
          objects_that_keep_tag.insert(obj);
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
    if (objects_that_keep_tag.count(obj) == 0) {
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

// ClosureQueryConfig::evaluate - BFS from source through edge_filter
std::vector<GridObject*> ClosureQueryConfig::evaluate(const HandlerContext& ctx) const {
  assert(source && "ClosureQueryConfig requires a non-null source query");

  auto roots = source->evaluate(ctx);

  int max_distance = (radius == 0) ? std::numeric_limits<int>::max() : static_cast<int>(radius);
  std::unordered_map<GridObject*, int> distances;
  std::queue<GridObject*> frontier;

  for (auto* obj : roots) {
    if (distances.find(obj) == distances.end()) {
      distances[obj] = 0;
      frontier.push(obj);
    }
  }

  Grid* grid = ctx.grid;

  while (!frontier.empty()) {
    GridObject* current = frontier.front();
    frontier.pop();
    int current_dist = distances[current];

    if (current_dist >= max_distance) continue;

    // Check only immediate 8-connected neighbors
    for (int dr = -1; dr <= 1; ++dr) {
      for (int dc = -1; dc <= 1; ++dc) {
        if (dr == 0 && dc == 0) continue;

        int nr = static_cast<int>(current->location.r) + dr;
        int nc = static_cast<int>(current->location.c) + dc;

        if (nr < 0 || nr >= grid->height || nc < 0 || nc >= grid->width) continue;

        GridObject* neighbor = grid->object_at(GridLocation(static_cast<GridCoord>(nr), static_cast<GridCoord>(nc)));
        if (!neighbor || distances.count(neighbor)) continue;

        // Empty edge_filter means no expansion (only roots get the tag);
        // otherwise matches_filters would return true for all neighbors and
        // incorrectly include agents/other objects.
        if (!edge_filter.empty() && QuerySystem::matches_filters(neighbor, edge_filter, ctx)) {
          distances[neighbor] = current_dist + 1;
          frontier.push(neighbor);
        }
      }
    }
  }

  std::vector<GridObject*> visited;
  visited.reserve(distances.size());
  for (const auto& [obj, _] : distances) {
    visited.push_back(obj);
  }

  // Optionally restrict result to objects that pass result_filters (e.g. junction-only)
  if (!result_filters.empty()) {
    std::vector<GridObject*> filtered;
    for (auto* obj : visited) {
      if (QuerySystem::matches_filters(obj, result_filters, ctx)) {
        filtered.push_back(obj);
      }
    }
    visited = std::move(filtered);
  }

  return QuerySystem::apply_limits(std::move(visited), max_items, order_by, ctx);
}

}  // namespace mettagrid
