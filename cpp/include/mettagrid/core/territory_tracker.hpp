#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_TERRITORY_TRACKER_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_TERRITORY_TRACKER_HPP_

#include <memory>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "core/grid_object.hpp"
#include "handler/handler_context.hpp"
#include "handler/territory_config.hpp"

namespace mettagrid {

class Filter;
class Mutation;

struct InstantiatedHandler {
  std::vector<std::unique_ptr<Filter>> filters;
  std::vector<std::unique_ptr<Mutation>> mutations;
};

struct TerritorySource {
  GridObject* source;
  TerritoryControlConfig control;
  int territory_index;
};

struct CellOwnership {
  int winning_tag = -1;
  int64_t winning_score = 0;
};

/**
 * TerritoryTracker manages territory influence zones.
 *
 * Territory types are defined at the game level (TerritoryConfig). Objects
 * register TerritoryControlConfigs that project influence onto nearby cells.
 * Per-cell ownership is computed by grouping controlling objects by their
 * matching tag, summing strengths after distance decay, and choosing the
 * tag with the highest total.
 *
 * Provides:
 *   1. Observation masks (friendly/enemy/neutral per tile)
 *   2. Per-tick handler effects (on_enter, on_exit, presence)
 *
 * Handlers fire with actor = proxy cell object (carries winning tag),
 * target = affected agent. Handlers use filters (e.g. sharedTagPrefix)
 * to distinguish friendly vs enemy territory — the tracker itself is
 * team-agnostic.
 */
class TerritoryTracker {
public:
  TerritoryTracker(GridCoord height, GridCoord width, const std::vector<TerritoryConfig>& territory_configs);
  ~TerritoryTracker();

  void register_source(GridObject& source, const TerritoryControlConfig& control);
  void unregister_source(GridObject& source);
  void notify_source_moved(GridObject& source, const GridLocation& old_location);

  void compute_observability_at(const GridLocation& loc,
                                GridObject& observer,
                                ObservationType* out_territory_mask) const;

  void apply_effects(GridObject& target, HandlerContext& ctx);

  size_t source_count_at(const GridLocation& loc, int territory_index) const;

private:
  GridCoord _height;
  GridCoord _width;
  size_t _num_territories;

  std::vector<TerritoryConfig> _territory_configs;

  // Per territory type: instantiated handlers from game-level config
  struct TerritoryHandlers {
    std::vector<InstantiatedHandler> on_enter;
    std::vector<InstantiatedHandler> on_exit;
    std::vector<InstantiatedHandler> presence;
  };
  std::vector<TerritoryHandlers> _handlers;

  // Per territory type: proxy GridObject used as handler actor
  std::vector<std::unique_ptr<GridObject>> _proxy_cells;

  // Per cell per territory: list of sources influencing that cell
  // Layout: _cell_sources[r][c][territory_index] -> vector<shared_ptr<TerritorySource>>
  std::vector<std::vector<std::vector<std::vector<std::shared_ptr<TerritorySource>>>>> _cell_sources;

  // All sources registered by a given object
  std::unordered_map<GridObject*, std::vector<std::shared_ptr<TerritorySource>>> _sources_by_object;

  // Enter/exit tracking: per agent per territory_index, the winning tag the agent is currently "inside"
  // -1 means agent is not in any owned territory for that type.
  // Key: target GridObject*, Value: map from territory_index to winning_tag_id
  std::unordered_map<GridObject*, std::unordered_map<int, int>> _inside_tag;

  CellOwnership compute_cell_ownership(const GridLocation& loc, int territory_index) const;

  void remove_source_from_cells(GridObject& source,
                                const GridLocation& loc,
                                const std::vector<std::shared_ptr<TerritorySource>>& sources);

  static bool has_tag_with_prefix(const GridObject& obj, const std::vector<int>& prefix_ids);
  static int find_matching_tag(const GridObject& obj, const std::vector<int>& prefix_ids);
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_TERRITORY_TRACKER_HPP_
