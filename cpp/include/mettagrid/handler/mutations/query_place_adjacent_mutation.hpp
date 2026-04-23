#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_QUERY_PLACE_ADJACENT_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_QUERY_PLACE_ADJACENT_MUTATION_HPP_

#include <array>

#include "core/grid.hpp"
#include "core/grid_object.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation.hpp"

namespace mettagrid {

class QueryPlaceAdjacentMutation : public Mutation {
public:
  explicit QueryPlaceAdjacentMutation(const QueryPlaceAdjacentMutationConfig& config) : _config(config) {}

  void apply(HandlerContext& ctx) override {
    auto* entity = ctx.resolve(_config.target);
    if (entity == nullptr || ctx.grid == nullptr || _config.query == nullptr) {
      return;
    }

    auto results = _config.query->evaluate(ctx);
    for (GridObject* destination : results) {
      if (destination == nullptr || destination == entity) {
        continue;
      }

      GridLocation next_loc;
      if (_find_adjacent_location(*entity, *destination, *ctx.grid, next_loc)) {
        ctx.grid->move_object(*entity, next_loc);
        return;
      }
    }
  }

private:
  static bool _find_adjacent_location(const GridObject& entity,
                                      const GridObject& destination,
                                      const Grid& grid,
                                      GridLocation& next_loc) {
    constexpr std::array<std::pair<int, int>, 4> kCardinalDeltas = {{
        {-1, 0},
        {1, 0},
        {0, -1},
        {0, 1},
    }};

    for (const auto& [dr, dc] : kCardinalDeltas) {
      int row = static_cast<int>(destination.location.r) + dr;
      int col = static_cast<int>(destination.location.c) + dc;
      if (row < 0 || col < 0) {
        continue;
      }
      GridLocation loc(static_cast<GridCoord>(row), static_cast<GridCoord>(col));
      if (!grid.is_valid_location(loc) || !grid.is_empty(loc.r, loc.c) || loc == entity.location) {
        continue;
      }
      next_loc = loc;
      return true;
    }
    return false;
  }

  QueryPlaceAdjacentMutationConfig _config;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_QUERY_PLACE_ADJACENT_MUTATION_HPP_
