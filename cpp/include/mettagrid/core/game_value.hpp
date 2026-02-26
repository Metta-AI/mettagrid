#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_GAME_VALUE_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_GAME_VALUE_HPP_

#include <string>
#include <vector>

#include "core/game_value_config.hpp"
#include "core/resolved_game_value.hpp"

class StatsTracker;
class HasInventory;

namespace mettagrid {
class HandlerContext;
}

// Resolve a GameValueConfig into a ResolvedGameValue that can be read repeatedly.
// Context provides all required dependencies (entity, trackers, query system).
ResolvedGameValue resolve_game_value(const GameValueConfig& gvc, const mettagrid::HandlerContext& ctx);

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_GAME_VALUE_HPP_
