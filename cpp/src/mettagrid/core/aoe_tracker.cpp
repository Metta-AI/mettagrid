#include "core/aoe_tracker.hpp"

#include <algorithm>
#include <cassert>
#include <cstdint>
#include <unordered_map>
#include <unordered_set>

#include "core/grid_object.hpp"
#include "handler/filters/filter_factory.hpp"
#include "handler/mutations/mutation_factory.hpp"
#include "systems/stats_tracker.hpp"

namespace mettagrid {
namespace {
// AOE model overview:
// - Every source owns one or more AOE configs (radius + filters + mutations).
// - Fixed sources (is_static=true) are pre-registered into _cell_effects so apply_fixed() is O(k) per tile.
// - Mobile sources are checked each tick in apply_mobile(), since their coverage moves.
// - Presence deltas are edge-triggered with _inside tracking (enter => +1, exit => -1).
// - Territory observation masks are handled separately by TerritoryTracker.
}  // namespace

// AOESource implementation

AOESource::AOESource(GridObject* src, const AOEConfig& cfg) : source(src), config(cfg) {
  // Instantiate filters
  for (const auto& filter_cfg : config.filters) {
    filters.push_back(create_filter(filter_cfg));
  }
  // Instantiate mutations
  for (const auto& mutation_cfg : config.mutations) {
    mutations.push_back(create_mutation(mutation_cfg));
  }
}

AOESource::~AOESource() = default;

AOESource::AOESource(AOESource&& other) noexcept
    : source(other.source),
      config(std::move(other.config)),
      filters(std::move(other.filters)),
      mutations(std::move(other.mutations)) {
  other.source = nullptr;
}

AOESource& AOESource::operator=(AOESource&& other) noexcept {
  if (this != &other) {
    source = other.source;
    config = std::move(other.config);
    filters = std::move(other.filters);
    mutations = std::move(other.mutations);
    other.source = nullptr;
  }
  return *this;
}

bool AOESource::try_apply(GridObject* target, const HandlerContext& ctx) {
  HandlerContext target_ctx = ctx;
  target_ctx.actor = source;
  target_ctx.target = target;

  for (const auto& filter : filters) {
    if (!filter->passes(target_ctx)) {
      return false;
    }
  }

  for (const auto& mutation : mutations) {
    mutation->apply(target_ctx);
  }

  return true;
}

bool AOESource::passes_filters(GridObject* target, const HandlerContext& ctx) const {
  HandlerContext target_ctx = ctx;
  target_ctx.actor = source;
  target_ctx.target = target;
  for (const auto& filter : filters) {
    if (!filter->passes(target_ctx)) {
      return false;
    }
  }
  return true;
}

void AOESource::apply_presence_deltas(GridObject* target, int multiplier) {
  for (const auto& delta : config.presence_deltas) {
    target->inventory.update(delta.resource_id, delta.delta * multiplier);
  }
}

// AOETracker implementation

AOETracker::AOETracker(GridCoord height, GridCoord width)
    : _height(height),
      _width(width),
      _cell_effects(height, std::vector<std::vector<std::shared_ptr<AOESource>>>(width)) {}

void AOETracker::register_source(GridObject& source, const AOEConfig& config) {
  if (config.is_static) {
    register_fixed(source, config);
  } else {
    register_mobile(source, config);
  }
}

void AOETracker::unregister_source(GridObject& source) {
  unregister_fixed(source);
  unregister_mobile(source);
}

void AOETracker::register_fixed(GridObject& source, const AOEConfig& config) {
  auto aoe_source = std::make_shared<AOESource>(&source, config);
  _fixed_sources[&source].push_back(aoe_source);

  const GridLocation& source_loc = source.location;
  int range = config.radius;

  int64_t range_sq = static_cast<int64_t>(range) * range;
  for (int dr = -range; dr <= range; ++dr) {
    int cell_r = static_cast<int>(source_loc.r) + dr;
    if (cell_r < 0 || cell_r >= static_cast<int>(_height)) {
      continue;
    }
    for (int dc = -range; dc <= range; ++dc) {
      int cell_c = static_cast<int>(source_loc.c) + dc;
      if (cell_c < 0 || cell_c >= static_cast<int>(_width)) {
        continue;
      }
      int64_t dist_sq = static_cast<int64_t>(dr) * dr + static_cast<int64_t>(dc) * dc;
      if (dist_sq > range_sq) {
        continue;
      }
      _cell_effects[cell_r][cell_c].push_back(aoe_source);
    }
  }
}

void AOETracker::register_mobile(GridObject& source, const AOEConfig& config) {
  auto aoe_source = std::make_shared<AOESource>(&source, config);
  _mobile_sources.push_back(aoe_source);
}

void AOETracker::unregister_fixed(GridObject& source) {
  auto sources_it = _fixed_sources.find(&source);
  if (sources_it == _fixed_sources.end()) {
    return;
  }

  // Get the maximum range from all configs for this source
  int max_range = 0;
  for (const auto& aoe_source : sources_it->second) {
    max_range = std::max(max_range, aoe_source->config.radius);
  }

  const GridLocation& source_loc = source.location;

  // Remove all AOE sources from this object from all cells within max range
  for (int dr = -max_range; dr <= max_range; ++dr) {
    int cell_r = static_cast<int>(source_loc.r) + dr;
    if (cell_r < 0 || cell_r >= static_cast<int>(_height)) {
      continue;
    }
    for (int dc = -max_range; dc <= max_range; ++dc) {
      int cell_c = static_cast<int>(source_loc.c) + dc;
      if (cell_c < 0 || cell_c >= static_cast<int>(_width)) {
        continue;
      }
      auto& effects = _cell_effects[cell_r][cell_c];
      effects.erase(std::remove_if(effects.begin(),
                                   effects.end(),
                                   [&source](const std::shared_ptr<AOESource>& e) { return e->source == &source; }),
                    effects.end());
    }
  }

  // Apply exit deltas to all targets currently inside this source's AOEs
  for (const auto& aoe_source : sources_it->second) {
    auto inside_it = _inside.find(aoe_source.get());
    if (inside_it != _inside.end()) {
      for (auto* target : inside_it->second) {
        aoe_source->apply_presence_deltas(target, -1);
        // Also clean up the reverse lookup
        auto target_it = _target_fixed_inside.find(target);
        if (target_it != _target_fixed_inside.end()) {
          target_it->second.erase(aoe_source.get());
        }
      }
      _inside.erase(inside_it);
    }
  }

  _fixed_sources.erase(sources_it);
}

void AOETracker::unregister_mobile(GridObject& source) {
  auto it = _mobile_sources.begin();
  while (it != _mobile_sources.end()) {
    if ((*it)->source == &source) {
      // Apply exit deltas to all targets currently inside
      auto inside_it = _inside.find(it->get());
      if (inside_it != _inside.end()) {
        for (auto* target : inside_it->second) {
          (*it)->apply_presence_deltas(target, -1);
        }
        _inside.erase(inside_it);
      }
      it = _mobile_sources.erase(it);
    } else {
      ++it;
    }
  }
}

void AOETracker::apply_fixed(GridObject& target, const HandlerContext& ctx) {
  HandlerContext target_ctx = ctx;
  target_ctx.actor = nullptr;
  target_ctx.target = &target;
  std::unordered_map<InventoryItem, InventoryDelta> deferred_target_resource_deltas;
  std::vector<InventoryItem> deferred_target_resource_order;
  std::unordered_set<InventoryItem> deferred_target_resource_seen;
  target_ctx.deferred_target_resource_deltas = &deferred_target_resource_deltas;
  target_ctx.deferred_target_resource_order = &deferred_target_resource_order;
  target_ctx.deferred_target_resource_seen = &deferred_target_resource_seen;

  // Get the set of fixed AOEs the target was previously inside
  auto& prev_inside = _target_fixed_inside[&target];

  // Get AOEs at current cell
  const auto& cell_effects = _cell_effects[target.location.r][target.location.c];

  // Build set of AOEs at current cell for O(1) exit detection.
  _scratch_current_cell_set.clear();
  _scratch_current_cell_set.reserve(cell_effects.size());
  for (const auto& aoe_sp : cell_effects) {
    _scratch_current_cell_set.insert(aoe_sp.get());
  }

  // Process exits for AOEs that were inside but are not at current cell
  for (auto it = prev_inside.begin(); it != prev_inside.end();) {
    AOESource* aoe_source = *it;
    if (_scratch_current_cell_set.find(aoe_source) == _scratch_current_cell_set.end()) {
      _inside[aoe_source].erase(&target);
      aoe_source->apply_presence_deltas(&target, -1);
      it = prev_inside.erase(it);
    } else {
      ++it;
    }
  }

  // Process all sources at this cell
  for (const auto& aoe_sp : cell_effects) {
    AOESource* aoe_source = aoe_sp.get();
    if (!aoe_source->has_mutations() && !aoe_source->has_presence_deltas()) {
      continue;
    }

    bool skip_self = (!aoe_source->config.effect_self && aoe_source->source == &target);
    bool now_passes = (!skip_self && aoe_source->passes_filters(&target, target_ctx));

    bool was_inside = prev_inside.contains(aoe_source);
    if (now_passes && !was_inside) {
      _inside[aoe_source].insert(&target);
      aoe_source->apply_presence_deltas(&target, +1);
      prev_inside.insert(aoe_source);
    } else if (!now_passes && was_inside) {
      _inside[aoe_source].erase(&target);
      aoe_source->apply_presence_deltas(&target, -1);
      prev_inside.erase(aoe_source);
    }

    if (now_passes && aoe_source->has_mutations()) {
      aoe_source->try_apply(&target, target_ctx);
    }
  }

  // Apply net ResourceDeltaMutation deltas on target once, so clamping happens on the net result.
  if (!deferred_target_resource_order.empty()) {
    for (InventoryItem resource_id : deferred_target_resource_order) {
      auto it = deferred_target_resource_deltas.find(resource_id);
      if (it == deferred_target_resource_deltas.end()) {
        continue;
      }
      InventoryDelta delta = it->second;
      if (delta != 0) {
        target.inventory.update(resource_id, delta);
      }
    }
  }
}

void AOETracker::apply_mobile(const std::vector<Agent*>& agents, const HandlerContext& ctx) {
  HandlerContext mobile_ctx = ctx;
  mobile_ctx.actor = nullptr;
  mobile_ctx.target = nullptr;

  for (const auto& aoe_source : _mobile_sources) {
    const GridLocation& source_loc = aoe_source->source->location;
    int range = aoe_source->config.radius;

    // Get current inside set for this AOE
    auto& inside_set = _inside[aoe_source.get()];

    for (auto* agent : agents) {
      // Skip if target is the source and effect_self is false
      if (!aoe_source->config.effect_self && aoe_source->source == agent) {
        continue;
      }

      bool was_in = inside_set.contains(agent);

      // Check if agent is in range
      if (!in_range(source_loc, agent->location, range)) {
        if (was_in) {
          // Moved out of range.
          inside_set.erase(agent);
          aoe_source->apply_presence_deltas(agent, -1);
        }
        continue;
      }

      // Agent is in range, check filters
      bool now_passes = aoe_source->passes_filters(agent, mobile_ctx);

      if (now_passes) {
        if (!was_in) {
          // Enter event
          inside_set.insert(agent);
          aoe_source->apply_presence_deltas(agent, +1);
        }

        // Apply tick mutations
        if (aoe_source->has_mutations()) {
          aoe_source->try_apply(agent, mobile_ctx);
        }
      } else if (was_in) {
        // Was inside but filter no longer passes - exit
        inside_set.erase(agent);
        aoe_source->apply_presence_deltas(agent, -1);
      }
    }
  }
}

bool AOETracker::in_range(const GridLocation& source_loc, const GridLocation& target_loc, int range) {
  int64_t dr = static_cast<int64_t>(source_loc.r) - static_cast<int64_t>(target_loc.r);
  int64_t dc = static_cast<int64_t>(source_loc.c) - static_cast<int64_t>(target_loc.c);
  return (dr * dr + dc * dc) <= (static_cast<int64_t>(range) * range);
}

size_t AOETracker::fixed_effect_count_at(const GridLocation& loc) const {
  if (loc.r >= _height || loc.c >= _width) {
    return 0;
  }
  return _cell_effects[loc.r][loc.c].size();
}

}  // namespace mettagrid
