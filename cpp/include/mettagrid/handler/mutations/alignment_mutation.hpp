#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_ALIGNMENT_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_ALIGNMENT_MUTATION_HPP_

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
 * - Aligning to a specific collective by name (collective_name)
 */
class AlignmentMutation : public Mutation {
public:
  explicit AlignmentMutation(const AlignmentMutationConfig& config) : _config(config) {}

  // Set the resolved collective pointer (called during handler setup for named collectives)
  void set_collective(Collective* coll) {
    _resolved_collective = coll;
  }

  void apply(HandlerContext& ctx) override {
    // All GridObjects are Alignable - try to cast target to GridObject
    GridObject* target_obj = dynamic_cast<GridObject*>(ctx.target);
    if (target_obj == nullptr) {
      return;
    }

    Collective* old_collective = target_obj->getCollective();

    // If we have a resolved collective (from collective_name), use it
    if (_resolved_collective != nullptr) {
      if (old_collective != _resolved_collective) {
        target_obj->setCollective(_resolved_collective);
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
  Collective* _resolved_collective = nullptr;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_ALIGNMENT_MUTATION_HPP_
