#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_ALIGNMENT_FILTER_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_ALIGNMENT_FILTER_HPP_

#include "core/grid_object.hpp"
#include "handler/filters/filter.hpp"
#include "handler/handler_config.hpp"
#include "objects/collective.hpp"

namespace mettagrid {

/**
 * AlignmentFilter: Check alignment relationships
 *
 * Extended to support:
 * - Checking if entity is aligned/unaligned
 * - Checking if actor and target have same/different collective
 * - Checking if entity belongs to a specific collective (by ID)
 *
 * For collective-specific checks, set collective_id >= 0.
 * Otherwise, uses condition-based checks.
 */
class AlignmentFilter : public Filter {
public:
  explicit AlignmentFilter(const AlignmentFilterConfig& config) : _config(config) {}

  bool passes(const HandlerContext& ctx) const override {
    // If collective_id is set, check if entity belongs to that specific collective
    if (_config.collective_id >= 0) {
      GridObject* grid_obj = dynamic_cast<GridObject*>(ctx.resolve(_config.entity));
      if (grid_obj == nullptr) {
        return false;
      }

      Collective* obj_collective = grid_obj->getCollective();
      // Look up the target collective from context
      Collective* target_collective = ctx.get_collective_by_id(_config.collective_id);
      return obj_collective != nullptr && obj_collective == target_collective;
    }

    // Otherwise, use condition-based alignment checks
    Collective* actor_coll = ctx.actor_collective();
    Collective* target_coll = ctx.target_collective();

    // Get the collective to check based on entity reference
    Collective* entity_coll = (_config.entity == EntityRef::actor) ? actor_coll : target_coll;

    switch (_config.condition) {
      case AlignmentCondition::aligned:
        // Check if the specified entity has a collective
        return entity_coll != nullptr;

      case AlignmentCondition::unaligned:
        // Check if the specified entity has no collective
        return entity_coll == nullptr;

      case AlignmentCondition::same_collective:
        // Both must have collectives and they must be the same
        return actor_coll != nullptr && actor_coll == target_coll;

      case AlignmentCondition::different_collective:
        // Both must have collectives and they must be different
        return actor_coll != nullptr && target_coll != nullptr && actor_coll != target_coll;

      default:
        return false;
    }
  }

private:
  AlignmentFilterConfig _config;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_ALIGNMENT_FILTER_HPP_
