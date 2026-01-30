#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_GAME_VALUE_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_GAME_VALUE_MUTATION_HPP_

#include <stdexcept>

#include "core/game_value_config.hpp"
#include "handler/handler_config.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation.hpp"
#include "objects/agent.hpp"
#include "objects/collective.hpp"

namespace mettagrid {

/**
 * GameValueMutation: Apply a delta to a game value (inventory or stat).
 *
 * Resolves the target entity and value at apply time.
 */
class GameValueMutation : public Mutation {
public:
  explicit GameValueMutation(const GameValueMutationConfig& config) : _config(config) {}

  void apply(HandlerContext& ctx) override {
    HasInventory* entity = ctx.resolve(_config.entity);

    switch (_config.value.type) {
      case GameValueType::INVENTORY: {
        if (entity == nullptr) return;
        entity->inventory.update(_config.value.id, static_cast<InventoryDelta>(_config.delta));
        break;
      }
      case GameValueType::STAT: {
        StatsTracker* tracker = ctx.resolve_stats_tracker(_config.value.scope, entity);
        if (tracker == nullptr) return;
        if (!_config.value.stat_name.empty()) {
          tracker->add(_config.value.stat_name, _config.delta);
        } else {
          float* ptr = tracker->get_ptr(_config.value.id);
          if (ptr != nullptr) {
            *ptr += _config.delta;
          }
        }
        break;
      }
      case GameValueType::TAG_COUNT: {
        throw std::runtime_error("Cannot mutate TAG_COUNT game value (read-only)");
      }
    }
  }

private:
  GameValueMutationConfig _config;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_GAME_VALUE_MUTATION_HPP_
