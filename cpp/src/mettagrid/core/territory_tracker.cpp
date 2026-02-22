#include "core/territory_tracker.hpp"

#include <algorithm>
#include <cassert>
#include <cstdint>
#include <unordered_map>

#include "handler/filters/filter_factory.hpp"
#include "handler/mutations/mutation_factory.hpp"

namespace mettagrid {
namespace {

int64_t distance_sq(const GridLocation& a, const GridLocation& b) {
  int64_t dr = static_cast<int64_t>(a.r) - static_cast<int64_t>(b.r);
  int64_t dc = static_cast<int64_t>(a.c) - static_cast<int64_t>(b.c);
  return dr * dr + dc * dc;
}

uint64_t floor_sqrt_u64(uint64_t value) {
  uint64_t root = 0;
  uint64_t bit = 1ULL << 62;
  while (bit > value) {
    bit >>= 2;
  }
  while (bit != 0) {
    if (value >= root + bit) {
      value -= root + bit;
      root = (root >> 1) + bit;
    } else {
      root >>= 1;
    }
    bit >>= 2;
  }
  return root;
}

// New influence model: score = max(0, strength - decay * euclidean_distance)
// Uses integer scaling (1024x) for precision.
int64_t territory_influence_score(int strength, int decay, int64_t dist_sq) {
  assert(strength > 0 && "strength must be positive");
  assert(decay > 0 && "decay must be positive");
  assert(dist_sq >= 0 && "distance squared cannot be negative");
  constexpr uint64_t kScale = 1024;
  uint64_t scaled_dist_sq = static_cast<uint64_t>(dist_sq) * kScale * kScale;
  uint64_t scaled_distance = floor_sqrt_u64(scaled_dist_sq);
  int64_t score = static_cast<int64_t>(strength) * static_cast<int64_t>(kScale) -
                  static_cast<int64_t>(decay) * static_cast<int64_t>(scaled_distance);
  return score > 0 ? score : 0;
}

int effective_radius(int strength, int decay) {
  return (decay > 0) ? (strength / decay) : strength;
}

InstantiatedHandler instantiate_handler(const HandlerConfig& cfg) {
  InstantiatedHandler h;
  for (const auto& fc : cfg.filters) {
    h.filters.push_back(create_filter(fc));
  }
  for (const auto& mc : cfg.mutations) {
    h.mutations.push_back(create_mutation(mc));
  }
  return h;
}

bool passes_filters(const std::vector<std::unique_ptr<Filter>>& filters, const HandlerContext& ctx) {
  for (const auto& f : filters) {
    if (!f->passes(ctx)) return false;
  }
  return true;
}

void apply_mutations(const std::vector<std::unique_ptr<Mutation>>& mutations, HandlerContext& ctx) {
  for (const auto& m : mutations) {
    m->apply(ctx);
  }
}

}  // namespace

// TerritoryTracker

TerritoryTracker::TerritoryTracker(GridCoord height,
                                   GridCoord width,
                                   const std::vector<TerritoryConfig>& territory_configs)
    : _height(height),
      _width(width),
      _num_territories(territory_configs.size()),
      _territory_configs(territory_configs) {
  // Initialize cell_sources: [r][c][territory_index] -> empty vector
  _cell_sources.resize(height);
  for (GridCoord r = 0; r < height; ++r) {
    _cell_sources[r].resize(width);
    for (GridCoord c = 0; c < width; ++c) {
      _cell_sources[r][c].resize(_num_territories);
    }
  }

  // Instantiate handlers and proxy cells for each territory type
  _handlers.resize(_num_territories);
  _proxy_cells.resize(_num_territories);
  for (size_t ti = 0; ti < _num_territories; ++ti) {
    const auto& tc = _territory_configs[ti];

    for (const auto& hc : tc.on_enter) {
      _handlers[ti].on_enter.push_back(instantiate_handler(hc));
    }
    for (const auto& hc : tc.on_exit) {
      _handlers[ti].on_exit.push_back(instantiate_handler(hc));
    }
    for (const auto& hc : tc.presence) {
      _handlers[ti].presence.push_back(instantiate_handler(hc));
    }

    // Create proxy cell GridObject for this territory type
    _proxy_cells[ti] = std::make_unique<GridObject>();
    _proxy_cells[ti]->type_name = "territory_cell";
    _proxy_cells[ti]->name = "territory_cell";
  }
}

TerritoryTracker::~TerritoryTracker() = default;

void TerritoryTracker::register_source(GridObject& source, const TerritoryControlConfig& control) {
  int ti = control.territory_index;
  assert(ti >= 0 && static_cast<size_t>(ti) < _num_territories);

  auto ts = std::make_shared<TerritorySource>();
  ts->source = &source;
  ts->control = control;
  ts->territory_index = ti;
  _sources_by_object[&source].push_back(ts);

  int range = effective_radius(control.strength, control.decay);
  int64_t range_sq = static_cast<int64_t>(range) * range;

  const GridLocation& loc = source.location;
  for (int dr = -range; dr <= range; ++dr) {
    int cell_r = static_cast<int>(loc.r) + dr;
    if (cell_r < 0 || cell_r >= static_cast<int>(_height)) continue;
    for (int dc = -range; dc <= range; ++dc) {
      int cell_c = static_cast<int>(loc.c) + dc;
      if (cell_c < 0 || cell_c >= static_cast<int>(_width)) continue;
      int64_t dsq = static_cast<int64_t>(dr) * dr + static_cast<int64_t>(dc) * dc;
      if (dsq > range_sq) continue;
      _cell_sources[cell_r][cell_c][ti].push_back(ts);
    }
  }
}

void TerritoryTracker::remove_source_from_cells(GridObject& source,
                                                const GridLocation& loc,
                                                const std::vector<std::shared_ptr<TerritorySource>>& sources) {
  std::unordered_map<int, int> max_range_per_territory;
  for (const auto& ts : sources) {
    int range = effective_radius(ts->control.strength, ts->control.decay);
    max_range_per_territory[ts->territory_index] = std::max(max_range_per_territory[ts->territory_index], range);
  }

  for (const auto& [ti, max_range] : max_range_per_territory) {
    for (int dr = -max_range; dr <= max_range; ++dr) {
      int cell_r = static_cast<int>(loc.r) + dr;
      if (cell_r < 0 || cell_r >= static_cast<int>(_height)) continue;
      for (int dc = -max_range; dc <= max_range; ++dc) {
        int cell_c = static_cast<int>(loc.c) + dc;
        if (cell_c < 0 || cell_c >= static_cast<int>(_width)) continue;
        auto& effects = _cell_sources[cell_r][cell_c][ti];
        effects.erase(
            std::remove_if(effects.begin(),
                           effects.end(),
                           [&source](const std::shared_ptr<TerritorySource>& e) { return e->source == &source; }),
            effects.end());
      }
    }
  }
}

void TerritoryTracker::unregister_source(GridObject& source) {
  auto it = _sources_by_object.find(&source);
  if (it == _sources_by_object.end()) return;

  remove_source_from_cells(source, source.location, it->second);
  _sources_by_object.erase(it);
}

void TerritoryTracker::notify_source_moved(GridObject& source, const GridLocation& old_location) {
  auto it = _sources_by_object.find(&source);
  if (it == _sources_by_object.end()) return;

  remove_source_from_cells(source, old_location, it->second);

  auto controls = std::move(it->second);
  _sources_by_object.erase(it);

  for (const auto& ts : controls) {
    register_source(source, ts->control);
  }
}

bool TerritoryTracker::has_tag_with_prefix(const GridObject& obj, const std::vector<int>& prefix_ids) {
  for (int tag_id : prefix_ids) {
    if (obj.has_tag(tag_id)) return true;
  }
  return false;
}

int TerritoryTracker::find_matching_tag(const GridObject& obj, const std::vector<int>& prefix_ids) {
  for (int tag_id : prefix_ids) {
    if (obj.has_tag(tag_id)) return tag_id;
  }
  return -1;
}

CellOwnership TerritoryTracker::compute_cell_ownership(const GridLocation& loc, int territory_index) const {
  CellOwnership result;
  if (loc.r >= _height || loc.c >= _width) return result;
  if (territory_index < 0 || static_cast<size_t>(territory_index) >= _num_territories) return result;

  const auto& prefix_ids = _territory_configs[territory_index].tag_prefix_ids;
  const auto& cell = _cell_sources[loc.r][loc.c][territory_index];

  // Sum scores per tag
  std::unordered_map<int, int64_t> tag_scores;
  for (const auto& ts : cell) {
    if (ts->source == nullptr) continue;
    int tag = find_matching_tag(*ts->source, prefix_ids);
    if (tag < 0) continue;
    int64_t score =
        territory_influence_score(ts->control.strength, ts->control.decay, distance_sq(ts->source->location, loc));
    if (score > 0) {
      tag_scores[tag] += score;
    }
  }

  // Find the tag with the highest total score; ties = no winner
  bool tied = false;
  for (const auto& [tag, score] : tag_scores) {
    if (score > result.winning_score) {
      result.winning_tag = tag;
      result.winning_score = score;
      tied = false;
    } else if (score == result.winning_score && result.winning_tag >= 0) {
      tied = true;
    }
  }
  if (tied) {
    result.winning_tag = -1;
    result.winning_score = 0;
  }
  return result;
}

void TerritoryTracker::compute_observability_at(const GridLocation& loc,
                                                GridObject& observer,
                                                ObservationType* out_territory_mask) const {
  if (out_territory_mask != nullptr) {
    *out_territory_mask = 0;
  }
  if (out_territory_mask == nullptr) return;

  for (size_t ti = 0; ti < _num_territories; ++ti) {
    auto cell_own = compute_cell_ownership(loc, static_cast<int>(ti));
    if (cell_own.winning_tag < 0) continue;

    if (observer.has_tag(cell_own.winning_tag)) {
      *out_territory_mask = 1;  // friendly
    } else {
      *out_territory_mask = 2;  // enemy
    }
    return;
  }
}

void TerritoryTracker::apply_effects(GridObject& target, HandlerContext& ctx) {
  auto& prev_tags = _inside_tag[&target];

  for (size_t ti = 0; ti < _num_territories; ++ti) {
    int ti_key = static_cast<int>(ti);
    auto cell_own = compute_cell_ownership(target.location, ti_key);

    int prev_tag = -1;
    auto prev_it = prev_tags.find(ti_key);
    if (prev_it != prev_tags.end()) {
      prev_tag = prev_it->second;
    }

    int cur_tag = cell_own.winning_tag;
    bool tag_changed = (prev_tag != cur_tag);

    if (tag_changed && prev_tag >= 0) {
      // EXIT: was in owned territory, either left or ownership flipped
      _proxy_cells[ti]->tag_bits.reset();
      _proxy_cells[ti]->tag_bits.set(prev_tag);
      _proxy_cells[ti]->location = target.location;

      HandlerContext tc = ctx;
      tc.actor = _proxy_cells[ti].get();
      tc.target = &target;
      for (const auto& handler : _handlers[ti].on_exit) {
        if (passes_filters(handler.filters, tc)) {
          apply_mutations(handler.mutations, tc);
        }
      }
    }

    if (tag_changed && cur_tag >= 0) {
      // ENTER: newly in owned territory (or ownership flipped to new tag)
      _proxy_cells[ti]->tag_bits.reset();
      _proxy_cells[ti]->tag_bits.set(cur_tag);
      _proxy_cells[ti]->location = target.location;

      HandlerContext tc = ctx;
      tc.actor = _proxy_cells[ti].get();
      tc.target = &target;
      for (const auto& handler : _handlers[ti].on_enter) {
        if (passes_filters(handler.filters, tc)) {
          apply_mutations(handler.mutations, tc);
        }
      }
    }

    // Update tracking
    if (cur_tag >= 0) {
      prev_tags[ti_key] = cur_tag;
    } else {
      prev_tags.erase(ti_key);
    }

    if (cur_tag >= 0) {
      // PRESENCE: every tick while in any owned territory
      _proxy_cells[ti]->tag_bits.reset();
      _proxy_cells[ti]->tag_bits.set(cur_tag);
      _proxy_cells[ti]->location = target.location;

      HandlerContext tc = ctx;
      tc.actor = _proxy_cells[ti].get();
      tc.target = &target;
      for (const auto& handler : _handlers[ti].presence) {
        if (passes_filters(handler.filters, tc)) {
          apply_mutations(handler.mutations, tc);
        }
      }
    }
  }
}

size_t TerritoryTracker::source_count_at(const GridLocation& loc, int territory_index) const {
  if (loc.r >= _height || loc.c >= _width) return 0;
  if (territory_index < 0 || static_cast<size_t>(territory_index) >= _num_territories) return 0;
  return _cell_sources[loc.r][loc.c][territory_index].size();
}

}  // namespace mettagrid
