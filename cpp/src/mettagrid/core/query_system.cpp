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

bool QuerySystem::matches_edge_filters(GridObject* source,
                                       GridObject* candidate,
                                       const std::vector<FilterConfig>& filter_configs,
                                       const HandlerContext& ctx) {
  if (filter_configs.empty()) {
    return true;
  }

  HandlerContext edge_ctx = ctx;
  edge_ctx.actor = source;
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

// ClosureQueryConfig::evaluate - BFS from source through candidates.
// Edge filters are binary: evaluated with actor=net_member, target=candidate.
std::vector<GridObject*> ClosureQueryConfig::evaluate(const HandlerContext& ctx) const {
  assert(source && "ClosureQueryConfig requires a non-null source query");
  assert(candidates && "ClosureQueryConfig requires a non-null candidates query");

  auto roots = source->evaluate(ctx);
  auto candidate_pool = candidates->evaluate(ctx);

  std::unordered_set<GridObject*> visited;
  std::queue<GridObject*> frontier;

  for (auto* obj : roots) {
    if (visited.insert(obj).second) {
      frontier.push(obj);
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
    }
  }

  std::vector<GridObject*> result;
  result.reserve(visited.size());
  for (auto* obj : visited) {
    result.push_back(obj);
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

}  // namespace mettagrid
