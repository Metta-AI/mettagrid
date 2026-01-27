#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_GRID_OBJECT_FACTORY_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_GRID_OBJECT_FACTORY_HPP_

#include <string>
#include <vector>

#include "core/grid_object.hpp"
#include "core/tag_index.hpp"
#include "core/types.hpp"

// Forward declarations
class StatsTracker;
class Grid;
class ObservationEncoder;
class Collective;

namespace mettagrid {

// Factory for creating GridObjects from config.
// Sets up grid, obs_encoder, current_timestep_ptr, and collective on objects that need them.
// Returns the created object. Caller is responsible for:
// - Adding to grid
// - Agent-specific setup (agent_id, add_agent)
// - Incrementing stats
// - Registering AOEs
GridObject* create_object_from_config(GridCoord r,
                                      GridCoord c,
                                      const GridObjectConfig* config,
                                      StatsTracker* stats,
                                      const std::vector<std::string>* resource_names,
                                      Grid* grid,
                                      const ObservationEncoder* obs_encoder,
                                      unsigned int* current_timestep_ptr,
                                      TagIndex* tag_index,
                                      const std::vector<Collective*>* collectives_by_id);

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_GRID_OBJECT_FACTORY_HPP_
