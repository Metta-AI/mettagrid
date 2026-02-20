#include "core/aoe_tracker.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <unordered_map>
#include <unordered_set>

#include "core/grid_object.hpp"
#include "handler/filters/filter_factory.hpp"
#include "handler/mutations/mutation_factory.hpp"
#include "systems/stats_tracker.hpp"

namespace mettagrid {
namespace {
int distance_sq(const GridLocation& a, const GridLocation& b) {
  int dr = std::abs(static_cast<int>(a.r) - static_cast<int>(b.r));
  int dc = std::abs(static_cast<int>(a.c) - static_cast<int>(b.c));
  return dr * dr + dc * dc;
}

bool is_territory_aoe(const AOESource* aoe_source) {
  return aoe_source != nullptr && aoe_source->config.controls_territory;
}

enum class TerritoryOwner {
  Neutral,
  Friendly,
  Enemy,
};

struct TerritoryContest {
  bool friendly_present = false;
  bool enemy_present = false;
  int friendly_best_key = std::numeric_limits<int>::max();
  int enemy_best_key = std::numeric_limits<int>::max();

  void consider(bool is_friendly, int key) {
    if (is_friendly) {
      friendly_present = true;
      if (key < friendly_best_key) {
        friendly_best_key = key;
      }
      return;
    }

    enemy_present = true;
    if (key < enemy_best_key) {
      enemy_best_key = key;
    }
  }

  TerritoryOwner owner() const {
    if (friendly_present && enemy_present) {
      if (friendly_best_key < enemy_best_key) {
        return TerritoryOwner::Friendly;
      }
      if (enemy_best_key < friendly_best_key) {
        return TerritoryOwner::Enemy;
      }
      return TerritoryOwner::Neutral;
    }
    if (friendly_present) {
      return TerritoryOwner::Friendly;
    }
    if (enemy_present) {
      return TerritoryOwner::Enemy;
    }
    return TerritoryOwner::Neutral;
  }
};
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

  // Register at all cells within Euclidean radius.
  int range_sq = range * range;
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
      int dist_sq = dr * dr + dc * dc;
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

  Collective* target_collective = target.getCollective();
  int target_collective_id = target_collective != nullptr ? target_collective->id : -1;
  bool territory_collapse_enabled = (target_collective_id >= 0);

  // Get the set of fixed AOEs the target was previously inside
  auto& prev_inside = _target_fixed_inside[&target];

  // Get AOEs at current cell
  const auto& cell_effects = _cell_effects[target.location.r][target.location.c];

  // Build set of AOEs at current cell for O(1) lookup, and partition sources by team.
  // Reuse scratch containers to avoid allocations in the per-agent hot path.
  _scratch_current_cell_set.clear();
  _scratch_enemy_sources.clear();
  _scratch_friendly_sources.clear();
  _scratch_other_sources.clear();
  _scratch_current_cell_set.reserve(cell_effects.size());
  _scratch_enemy_sources.reserve(cell_effects.size());
  _scratch_friendly_sources.reserve(cell_effects.size());
  _scratch_other_sources.reserve(cell_effects.size());

  for (const auto& aoe_sp : cell_effects) {
    AOESource* aoe_source = aoe_sp.get();
    _scratch_current_cell_set.insert(aoe_source);

    if (target_collective_id >= 0 && aoe_source->source != nullptr) {
      Collective* source_collective = aoe_source->source->getCollective();
      if (source_collective != nullptr) {
        if (source_collective->id == target_collective_id) {
          _scratch_friendly_sources.push_back(aoe_source);
        } else {
          _scratch_enemy_sources.push_back(aoe_source);
        }
        continue;
      }
    }
    _scratch_other_sources.push_back(aoe_source);
  }

  // Process exits for AOEs that were inside but are not at current cell
  // (target moved out of range)
  for (auto it = prev_inside.begin(); it != prev_inside.end();) {
    AOESource* aoe_source = *it;
    if (_scratch_current_cell_set.find(aoe_source) == _scratch_current_cell_set.end()) {
      // AOE was inside but is not at current cell - target moved out of range
      _inside[aoe_source].erase(&target);
      aoe_source->apply_presence_deltas(&target, -1);
      it = prev_inside.erase(it);
    } else {
      ++it;
    }
  }

  // Territory selection: collapse to a single winning side per tile/target.
  TerritoryContest territory_contest;

  if (territory_collapse_enabled) {
    auto consider_territory = [&](AOESource* aoe_source, bool is_friendly) {
      if (!is_territory_aoe(aoe_source) || aoe_source->source == nullptr) {
        return;
      }

      Collective* source_collective = aoe_source->source->getCollective();
      if (source_collective == nullptr) {
        return;
      }

      bool skip_self = (!aoe_source->config.effect_self && aoe_source->source == &target);
      if (skip_self || !aoe_source->passes_filters(&target, target_ctx)) {
        return;
      }

      territory_contest.consider(is_friendly, distance_sq(aoe_source->source->location, target.location));
    };

    for (AOESource* aoe_source : _scratch_friendly_sources) {
      consider_territory(aoe_source, true);
    }
    for (AOESource* aoe_source : _scratch_enemy_sources) {
      consider_territory(aoe_source, false);
    }
  }

  TerritoryOwner territory_owner = territory_collapse_enabled ? territory_contest.owner() : TerritoryOwner::Neutral;

  auto process_source = [&](AOESource* aoe_source) {
    if (!aoe_source->has_mutations() && !aoe_source->has_presence_deltas()) {
      return;
    }

    bool skip_self = (!aoe_source->config.effect_self && aoe_source->source == &target);
    bool now_passes = (!skip_self && aoe_source->passes_filters(&target, target_ctx));
    bool effective_passes = now_passes;

    if (territory_collapse_enabled && is_territory_aoe(aoe_source) && aoe_source->source != nullptr) {
      Collective* source_collective = aoe_source->source->getCollective();
      if (source_collective == nullptr) {
        effective_passes = false;
      } else {
        bool source_is_friendly = (source_collective->id == target_collective_id);
        bool territory_matches_source = (territory_owner == TerritoryOwner::Friendly && source_is_friendly) ||
                                        (territory_owner == TerritoryOwner::Enemy && !source_is_friendly);
        effective_passes = now_passes && territory_matches_source;
      }
    }

    bool was_inside = prev_inside.contains(aoe_source);
    if (effective_passes && !was_inside) {
      _inside[aoe_source].insert(&target);
      aoe_source->apply_presence_deltas(&target, +1);
      prev_inside.insert(aoe_source);
    } else if (!effective_passes && was_inside) {
      // Exit event (filter no longer passes, or lost a territory "fight")
      _inside[aoe_source].erase(&target);
      aoe_source->apply_presence_deltas(&target, -1);
      prev_inside.erase(aoe_source);
    }

    if (effective_passes && aoe_source->has_mutations()) {
      aoe_source->try_apply(&target, target_ctx);
    }
  };

  // Enemy first, then other, then friendly.
  // This avoids "heal gets clamped to max HP, then enemy damage reduces HP" ordering artifacts.
  for (AOESource* aoe_source : _scratch_enemy_sources) {
    process_source(aoe_source);
  }
  for (AOESource* aoe_source : _scratch_other_sources) {
    process_source(aoe_source);
  }
  for (AOESource* aoe_source : _scratch_friendly_sources) {
    process_source(aoe_source);
  }

  // Apply net ResourceDeltaMutation deltas on target once, so clamping happens on the net result.
  // This avoids ordering artifacts when multiple fixed effects touch the same capped resource.
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
  int dr = std::abs(static_cast<int>(source_loc.r) - static_cast<int>(target_loc.r));
  int dc = std::abs(static_cast<int>(source_loc.c) - static_cast<int>(target_loc.c));
  return (dr * dr + dc * dc) <= (range * range);
}

size_t AOETracker::fixed_effect_count_at(const GridLocation& loc) const {
  if (loc.r >= _height || loc.c >= _width) {
    return 0;
  }
  return _cell_effects[loc.r][loc.c].size();
}

void AOETracker::fixed_observability_at(const GridLocation& loc,
                                        GridObject& observer,
                                        const HandlerContext& ctx,
                                        ObservationType* out_aoe_mask,
                                        ObservationType* out_territory) const {
  if (out_aoe_mask != nullptr) {
    *out_aoe_mask = 0;
  }
  if (out_territory != nullptr) {
    *out_territory = 0;
  }

  if ((out_aoe_mask == nullptr && out_territory == nullptr) || loc.r >= _height || loc.c >= _width) {
    return;
  }

  Collective* observer_collective = observer.getCollective();
  if (observer_collective == nullptr) {
    return;
  }

  const auto& cell_effects = _cell_effects[loc.r][loc.c];
  if (cell_effects.empty()) {
    return;
  }

  HandlerContext obs_ctx = ctx;
  obs_ctx.actor = nullptr;
  obs_ctx.target = &observer;

  TerritoryContest territory_contest;

  for (const auto& aoe_source : cell_effects) {
    GridObject* source = aoe_source->source;
    if (source == nullptr) {
      continue;
    }

    if (!is_territory_aoe(aoe_source.get())) {
      continue;
    }

    Collective* source_collective = source->getCollective();
    if (source_collective == nullptr) {
      continue;
    }

    if (!aoe_source->passes_filters(&observer, obs_ctx)) {
      continue;
    }

    bool is_friendly = (source_collective->id == observer_collective->id);
    territory_contest.consider(is_friendly, distance_sq(source->location, loc));
  }

  ObservationType aoe_value = 0;
  TerritoryOwner owner = territory_contest.owner();
  if (owner == TerritoryOwner::Friendly) {
    aoe_value = 1;
  } else if (owner == TerritoryOwner::Enemy) {
    aoe_value = 2;
  }

  if (out_aoe_mask != nullptr) {
    *out_aoe_mask = aoe_value;
  }
  if (out_territory != nullptr) {
    *out_territory = aoe_value;
  }
}

}  // namespace mettagrid
