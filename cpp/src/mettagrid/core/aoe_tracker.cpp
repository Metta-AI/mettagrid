#include "core/aoe_tracker.hpp"

#include <algorithm>
#include <cmath>

#include "core/grid_object.hpp"
#include "handler/filters/filter_factory.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation_factory.hpp"
#include "objects/has_inventory.hpp"
#include "systems/stats_tracker.hpp"

namespace mettagrid {

// AOESource implementation

AOESource::AOESource(GridObject* src, const AOEConfig& cfg, TagIndex* tag_index) : source(src), config(cfg) {
  // Instantiate filters
  for (const auto& filter_cfg : config.filters) {
    filters.push_back(create_filter(filter_cfg, tag_index));
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

bool AOESource::try_apply(GridObject* target, StatsTracker* game_stats) {
  // Create context: actor=source, target=affected object
  // Include game_stats for StatsMutation support
  HandlerContext ctx(source, target, game_stats);
  ctx.grid = source->grid();

  // Check all filters
  for (const auto& filter : filters) {
    if (!filter->passes(ctx)) {
      return false;
    }
  }

  // Apply all mutations
  for (const auto& mutation : mutations) {
    mutation->apply(ctx);
  }

  return true;
}

bool AOESource::passes_filters(GridObject* target) const {
  HandlerContext ctx(source, target);
  ctx.grid = source->grid();
  for (const auto& filter : filters) {
    if (!filter->passes(ctx)) {
      return false;
    }
  }
  return true;
}

void AOESource::apply_presence_deltas(GridObject* target, int multiplier) {
  auto* has_inv = dynamic_cast<HasInventory*>(target);
  if (!has_inv) {
    return;
  }

  for (const auto& delta : config.presence_deltas) {
    has_inv->inventory.update(delta.resource_id, delta.delta * multiplier);
  }
}

// AOETracker implementation

AOETracker::AOETracker(GridCoord height, GridCoord width, StatsTracker* game_stats, TagIndex* tag_index)
    : _height(height),
      _width(width),
      _game_stats(game_stats),
      _tag_index(tag_index),
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
  auto aoe_source = std::make_shared<AOESource>(&source, config, _tag_index);
  _fixed_sources[&source].push_back(aoe_source);

  const GridLocation& source_loc = source.location;
  int range = config.radius;

  // Register at all cells within L-infinity (Chebyshev) distance
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
      _cell_effects[cell_r][cell_c].push_back(aoe_source);
    }
  }
}

void AOETracker::register_mobile(GridObject& source, const AOEConfig& config) {
  auto aoe_source = std::make_shared<AOESource>(&source, config, _tag_index);
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

void AOETracker::apply_fixed(GridObject& target) {
  // Get the set of fixed AOEs the target was previously inside
  auto& prev_inside = _target_fixed_inside[&target];

  // Get AOEs at current cell
  const auto& cell_effects = _cell_effects[target.location.r][target.location.c];

  // Build set of AOEs at current cell for O(1) lookup
  std::unordered_set<AOESource*> current_cell_set;
  for (const auto& aoe : cell_effects) {
    current_cell_set.insert(aoe.get());
  }

  // Process exits for AOEs that were inside but are not at current cell
  // (target moved out of range)
  for (auto it = prev_inside.begin(); it != prev_inside.end();) {
    AOESource* aoe_source = *it;
    if (current_cell_set.find(aoe_source) == current_cell_set.end()) {
      // AOE was inside but is not at current cell - target moved out of range
      _inside[aoe_source].erase(&target);
      aoe_source->apply_presence_deltas(&target, -1);
      it = prev_inside.erase(it);
    } else {
      ++it;
    }
  }

  // Process AOEs at current cell
  for (const auto& aoe_source : cell_effects) {
    // Skip if target is the source and effect_self is false
    if (!aoe_source->config.effect_self && aoe_source->source == &target) {
      continue;
    }

    bool now_passes = aoe_source->passes_filters(&target);
    bool was_in = prev_inside.contains(aoe_source.get());

    if (now_passes && !was_in) {
      // Enter event
      _inside[aoe_source.get()].insert(&target);
      aoe_source->apply_presence_deltas(&target, +1);
      prev_inside.insert(aoe_source.get());
    } else if (!now_passes && was_in) {
      // Exit event (filter no longer passes)
      _inside[aoe_source.get()].erase(&target);
      aoe_source->apply_presence_deltas(&target, -1);
      prev_inside.erase(aoe_source.get());
    }

    // Apply tick mutations if inside and has mutations
    if (now_passes && aoe_source->has_mutations()) {
      aoe_source->try_apply(&target, _game_stats);
    }
  }
}

void AOETracker::apply_mobile(const std::vector<Agent*>& agents) {
  for (const auto& aoe_source : _mobile_sources) {
    const GridLocation& source_loc = aoe_source->source->location;
    int range = aoe_source->config.radius;

    // Get current inside set for this AOE
    auto& inside_set = _inside[aoe_source.get()];

    // Track which targets we've seen this tick (to detect exits)
    std::unordered_set<GridObject*> seen_this_tick;

    for (auto* agent : agents) {
      // Skip if target is the source and effect_self is false
      if (!aoe_source->config.effect_self && aoe_source->source == agent) {
        continue;
      }

      // Check if agent is in range
      if (!in_range(source_loc, agent->location, range)) {
        continue;
      }

      // Agent is in range, check filters
      bool now_passes = aoe_source->passes_filters(agent);
      bool was_in = inside_set.contains(agent);

      if (now_passes) {
        seen_this_tick.insert(agent);

        if (!was_in) {
          // Enter event
          inside_set.insert(agent);
          aoe_source->apply_presence_deltas(agent, +1);
        }

        // Apply tick mutations
        if (aoe_source->has_mutations()) {
          aoe_source->try_apply(agent, _game_stats);
        }
      } else if (was_in) {
        // Was inside but filter no longer passes - exit
        inside_set.erase(agent);
        aoe_source->apply_presence_deltas(agent, -1);
      }
    }

    // Process exits for targets that moved out of range
    for (auto it = inside_set.begin(); it != inside_set.end();) {
      if (seen_this_tick.find(*it) == seen_this_tick.end()) {
        // Target was inside but not seen this tick - moved out of range
        aoe_source->apply_presence_deltas(*it, -1);
        it = inside_set.erase(it);
      } else {
        ++it;
      }
    }
  }
}

bool AOETracker::in_range(const GridLocation& source_loc, const GridLocation& target_loc, int range) {
  int dr = std::abs(static_cast<int>(source_loc.r) - static_cast<int>(target_loc.r));
  int dc = std::abs(static_cast<int>(source_loc.c) - static_cast<int>(target_loc.c));
  return std::max(dr, dc) <= range;
}

size_t AOETracker::fixed_effect_count_at(const GridLocation& loc) const {
  if (loc.r >= _height || loc.c >= _width) {
    return 0;
  }
  return _cell_effects[loc.r][loc.c].size();
}

}  // namespace mettagrid
