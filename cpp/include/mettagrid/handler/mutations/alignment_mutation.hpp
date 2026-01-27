#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_ALIGNMENT_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_ALIGNMENT_MUTATION_HPP_

#include <algorithm>

#include "core/grid_object.hpp"
#include "handler/handler_config.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation.hpp"
#include "objects/agent.hpp"
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
    Collective* new_collective = old_collective;
    bool changed = false;

    // If collective_id is set, look it up from context and use it
    if (_config.collective_id >= 0) {
      Collective* target_collective = ctx.get_collective_by_id(_config.collective_id);
      if (target_collective != nullptr && old_collective != target_collective) {
        target_obj->setCollective(target_collective);
        new_collective = target_collective;
        changed = true;
      }
    } else {
      // Otherwise, use align_to
      switch (_config.align_to) {
        case AlignTo::actor_collective: {
          Collective* actor_coll = ctx.actor_collective();
          if (actor_coll != nullptr && old_collective != actor_coll) {
            target_obj->setCollective(actor_coll);
            new_collective = actor_coll;
            changed = true;
          }
          break;
        }
        case AlignTo::none:
          if (old_collective != nullptr) {
            target_obj->clearCollective();
            new_collective = nullptr;
            changed = true;
          }
          break;
      }
    }

    // Track per-agent alignment actions for credit assignment.
    // Note: This is intentionally based on target type_name so recipes can
    // reward e.g. "junction.aligned_by_agent" / "junction.scrambled_by_agent".
    if (!changed) {
      return;
    }

    Agent* actor_agent = dynamic_cast<Agent*>(ctx.actor);
    if (actor_agent == nullptr) {
      return;
    }

    if (new_collective == nullptr) {
      actor_agent->stats.incr(target_obj->type_name + ".scrambled_by_agent");
    } else {
      actor_agent->stats.incr(target_obj->type_name + ".aligned_by_agent");
    }
  }

private:
  AlignmentMutationConfig _config;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_ALIGNMENT_MUTATION_HPP_
