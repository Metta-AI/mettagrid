#include "core/query_system.hpp"

#include <algorithm>
#include <cassert>
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

QuerySystem::QuerySystem(Grid* grid, TagIndex* tag_index, std::mt19937* rng, const std::vector<QueryTagConfig>& configs)
    : _grid(grid), _tag_index(tag_index), _rng(rng) {
  _query_tags.reserve(configs.size());

  for (const auto& cfg : configs) {
    QueryTagDef def;
    def.tag_id = cfg.tag_id;
    def.query = cfg.query;
    _query_tags.push_back(std::move(def));
  }
}

bool QuerySystem::matches_filters(GridObject* obj, const std::vector<FilterConfig>& filter_configs) const {
  if (filter_configs.empty()) {
    return true;
  }

  HandlerContext ctx;
  ctx.actor = obj;
  ctx.target = obj;
  ctx.tag_index = _tag_index;
  ctx.grid = _grid;
  ctx.query_system = const_cast<QuerySystem*>(this);

  for (const auto& filter_cfg : filter_configs) {
    auto f = create_filter(filter_cfg, _tag_index);
    if (f && !f->passes(ctx)) {
      return false;
    }
  }
  return true;
}

std::vector<GridObject*> QuerySystem::apply_limits(std::vector<GridObject*> results,
                                                   int max_items,
                                                   QueryOrderBy order_by) const {
  if (order_by == QueryOrderBy::random && _rng != nullptr) {
    std::shuffle(results.begin(), results.end(), *_rng);
  }

  if (max_items > 0 && static_cast<int>(results.size()) > max_items) {
    results.resize(max_items);
  }

  return results;
}

void QuerySystem::compute_all() {
  _computing = true;

  for (const auto& def : _query_tags) {
    // Remove existing tag from all objects that have it
    auto tagged_objects = _tag_index->get_objects_with_tag(def.tag_id);
    for (auto* obj : tagged_objects) {
      obj->remove_tag(def.tag_id);
    }

    // Evaluate query and apply tag
    if (def.query) {
      auto result = def.query->evaluate(*this);
      for (auto* obj : result) {
        obj->add_tag(def.tag_id);
      }
    }
  }
  _computing = false;
}

void QuerySystem::recompute(int tag_id) {
  _computing = true;

  for (const auto& def : _query_tags) {
    if (def.tag_id == tag_id) {
      auto tagged_objects = _tag_index->get_objects_with_tag(def.tag_id);
      for (auto* obj : tagged_objects) {
        obj->remove_tag(def.tag_id);
      }

      if (def.query) {
        auto result = def.query->evaluate(*this);
        for (auto* obj : result) {
          obj->add_tag(def.tag_id);
        }
      }
      break;
    }
  }
  _computing = false;
}

// TagQueryConfig::evaluate - find objects with tag, apply filters and limits
std::vector<GridObject*> TagQueryConfig::evaluate(const QuerySystem& system) const {
  std::vector<GridObject*> result;
  const auto& candidates = system.tag_index()->get_objects_with_tag(tag_id);
  for (auto* obj : candidates) {
    if (system.matches_filters(obj, filters)) {
      result.push_back(obj);
    }
  }
  return system.apply_limits(std::move(result), max_items, order_by);
}

// ClosureQueryConfig::evaluate - BFS from source through edge_filter
std::vector<GridObject*> ClosureQueryConfig::evaluate(const QuerySystem& system) const {
  assert(source && "ClosureQueryConfig requires a non-null source query");

  auto roots = source->evaluate(system);

  int max_distance = (radius == 0) ? std::numeric_limits<int>::max() : static_cast<int>(radius);
  std::unordered_map<GridObject*, int> distances;
  std::queue<GridObject*> frontier;

  for (auto* obj : roots) {
    if (distances.find(obj) == distances.end()) {
      distances[obj] = 0;
      frontier.push(obj);
    }
  }

  Grid* grid = system.grid();

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

        // Empty edge_filter means no expansion (only roots get the tag)
        if (!edge_filter.empty() && system.matches_filters(neighbor, edge_filter)) {
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

  return system.apply_limits(std::move(visited), max_items, order_by);
}

}  // namespace mettagrid
