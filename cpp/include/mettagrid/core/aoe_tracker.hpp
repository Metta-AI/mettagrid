#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_AOE_TRACKER_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_AOE_TRACKER_HPP_

#include <memory>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "core/grid_object.hpp"
#include "core/tag_index.hpp"
#include "handler/handler_config.hpp"
#include "objects/agent.hpp"

// Forward declaration
class StatsTracker;

namespace mettagrid {

// Forward declarations
class Filter;
class Mutation;

/**
 * AOESource holds a reference to an AOE source and its processed config.
 * Used for both fixed (cell-based) and mobile AOE tracking.
 */
struct AOESource {
  GridObject* source;                                // The object emitting this AOE
  AOEConfig config;                                  // The AOE configuration
  std::vector<std::unique_ptr<Filter>> filters;      // Instantiated filters
  std::vector<std::unique_ptr<Mutation>> mutations;  // Instantiated mutations

  AOESource(GridObject* src, const AOEConfig& cfg, TagIndex* tag_index = nullptr);
  ~AOESource();

  // Move-only (due to unique_ptr members)
  AOESource(AOESource&& other) noexcept;
  AOESource& operator=(AOESource&& other) noexcept;
  AOESource(const AOESource&) = delete;
  AOESource& operator=(const AOESource&) = delete;

  // Try to apply this AOE's mutations to a target (checks filters first)
  // game_stats is passed to HandlerContext for StatsMutation support
  bool try_apply(GridObject* target, StatsTracker* game_stats = nullptr);

  // Check if target passes filters (without applying mutations)
  bool passes_filters(GridObject* target) const;

  // Check if this AOE has presence deltas
  bool has_presence_deltas() const {
    return !config.presence_deltas.empty();
  }

  // Check if this AOE has mutations
  bool has_mutations() const {
    return !mutations.empty();
  }

  // Apply presence deltas to target (multiplier: +1 for enter, -1 for exit)
  void apply_presence_deltas(GridObject* target, int multiplier);
};

/**
 * AOETracker manages both fixed (static) and mobile AOE effects.
 *
 * Fixed AOE (is_static=true): Pre-computed cell registration for static sources.
 *   - Efficient O(1) lookup per target location
 *   - Used for stationary objects like turrets, healing stations
 *
 * Mobile AOE (is_static=false): Source list checked each tick.
 *   - O(sources * targets) per tick
 *   - Used for moving objects like agents with auras
 *
 * Usage:
 *   1. Create AOETracker with grid dimensions
 *   2. Call register_source() when an AOE source is created
 *   3. Call unregister_source() when an AOE source is removed
 *   4. Each tick:
 *      - Call apply_fixed() for each potential target
 *      - Call apply_mobile() once with the agent list
 */
class AOETracker {
public:
  AOETracker(GridCoord height, GridCoord width, StatsTracker* game_stats = nullptr, TagIndex* tag_index = nullptr);
  ~AOETracker() = default;

  // Set the game stats tracker (for StatsMutation support)
  void set_game_stats(StatsTracker* stats) {
    _game_stats = stats;
  }

  // Register an AOE source - routes to fixed or mobile based on config.is_static
  void register_source(GridObject& source, const AOEConfig& config);

  // Unregister all AOE configs for a source (both fixed and mobile)
  void unregister_source(GridObject& source);

  // Apply all fixed AOE effects at the target's location
  // Handles enter/exit tracking for presence_deltas
  void apply_fixed(GridObject& target);

  // Apply all mobile AOE effects (checks all mobile sources against all agents)
  // Handles enter/exit tracking for presence_deltas
  void apply_mobile(const std::vector<Agent*>& agents);

  // Get number of fixed effect sources at a location (for testing/debugging)
  size_t fixed_effect_count_at(const GridLocation& loc) const;

  // Get number of mobile sources (for testing/debugging)
  size_t mobile_source_count() const {
    return _mobile_sources.size();
  }

  // Get number of targets currently inside an AOE (for testing/debugging)
  size_t targets_inside_count() const {
    size_t count = 0;
    for (const auto& [_, targets] : _inside) {
      count += targets.size();
    }
    return count;
  }

private:
  // Check if target is within Chebyshev distance of source
  static bool in_range(const GridLocation& source_loc, const GridLocation& target_loc, int range);

  // Register a fixed AOE (pre-compute affected cells)
  void register_fixed(GridObject& source, const AOEConfig& config);

  // Register a mobile AOE (add to source list)
  void register_mobile(GridObject& source, const AOEConfig& config);

  // Unregister fixed AOEs for a source
  void unregister_fixed(GridObject& source);

  // Unregister mobile AOEs for a source
  void unregister_mobile(GridObject& source);

  GridCoord _height;
  GridCoord _width;
  StatsTracker* _game_stats = nullptr;  // Game-level stats tracker (for StatsMutation)
  TagIndex* _tag_index = nullptr;       // Tag index (for NearFilter support)

  // Fixed AOE: 2D array from cell location to list of sources affecting that cell
  // Indexed as _cell_effects[row][col]
  std::vector<std::vector<std::vector<std::shared_ptr<AOESource>>>> _cell_effects;

  // Fixed AOE: map from source object to its AOE sources (for unregistration)
  std::unordered_map<GridObject*, std::vector<std::shared_ptr<AOESource>>> _fixed_sources;

  // Mobile AOE: list of AOE sources
  std::vector<std::shared_ptr<AOESource>> _mobile_sources;

  // Track which targets are currently "inside" each AOE (in range AND passing filters)
  // Used for presence_deltas enter/exit tracking
  std::unordered_map<AOESource*, std::unordered_set<GridObject*>> _inside;

  // Reverse lookup: which fixed AOEs is each target inside (for efficient exit detection)
  std::unordered_map<GridObject*, std::unordered_set<AOESource*>> _target_fixed_inside;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_AOE_TRACKER_HPP_
