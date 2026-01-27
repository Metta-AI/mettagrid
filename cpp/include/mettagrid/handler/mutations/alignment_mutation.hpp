#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_ALIGNMENT_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_ALIGNMENT_MUTATION_HPP_

#include <algorithm>

#include "core/grid_object.hpp"
#include "handler/handler_config.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation.hpp"
#include "objects/collective.hpp"

namespace mettagrid {

/**
 * AlignmentMutation: Change target's collective alignment
 *
 * Extended to support:
 * - Aligning to actor's collective (align_to = actor_collective)
 * - Removing alignment (align_to = none)
 * - Aligning to a specific collective by ID (collective_id)
 */
class AlignmentMutation : public Mutation {
public:
  explicit AlignmentMutation(const AlignmentMutationConfig& config) : _config(config) {}

  void apply(HandlerContext& ctx) override {
    // All GridObjects are Alignable - try to cast target to GridObject
    GridObject* target_obj = dynamic_cast<GridObject*>(ctx.target);
    if (target_obj == nullptr) {
      return;
    }

    Collective* old_collective = target_obj->getCollective();

    // If collective_id is set, look it up from context and use it
    if (_config.collective_id >= 0) {
      Collective* target_collective = ctx.get_collective_by_id(_config.collective_id);
      if (target_collective != nullptr && old_collective != target_collective) {
        target_obj->setCollective(target_collective);
      }
    } else {
      // Otherwise, use align_to
      switch (_config.align_to) {
        case AlignTo::actor_collective: {
          Collective* actor_coll = ctx.actor_collective();
          if (actor_coll != nullptr && old_collective != actor_coll) {
            target_obj->setCollective(actor_coll);
          }
          break;
        }
        case AlignTo::none:
          if (old_collective != nullptr) {
            target_obj->clearCollective();
          }
          break;
      }
    }
  }

private:
  AlignmentMutationConfig _config;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_ALIGNMENT_MUTATION_HPP_
