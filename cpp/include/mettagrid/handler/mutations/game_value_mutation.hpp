#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_GAME_VALUE_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_GAME_VALUE_MUTATION_HPP_

#include <stdexcept>
#include <type_traits>

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
    float delta = ctx.resolve_game_value(_config.source, _config.target);

    std::visit(
        [&](auto&& c) {
          using T = std::decay_t<decltype(c)>;
          if constexpr (std::is_same_v<T, InventoryValueConfig>) {
            HasInventory* entity = ctx.resolve(_config.target);
            if (!entity) return;
            entity->inventory.update(c.id, static_cast<InventoryDelta>(delta));
          } else if constexpr (std::is_same_v<T, StatValueConfig>) {
            HasInventory* entity = ctx.resolve(_config.target);
            StatsTracker* tracker = ctx.resolve_stats_tracker(c.scope, entity);
            if (!tracker) return;
            if (!c.stat_name.empty()) {
              tracker->add(c.stat_name, delta);
            } else {
              float* ptr = tracker->get_ptr(c.id);
              if (ptr) *ptr += delta;
            }
          } else if constexpr (std::is_same_v<T, TagCountValueConfig>) {
            throw std::runtime_error("Cannot mutate TAG_COUNT game value (read-only)");
          } else if constexpr (std::is_same_v<T, ConstValueConfig>) {
            throw std::runtime_error("Cannot mutate CONST game value (read-only)");
          } else if constexpr (std::is_same_v<T, QueryInventoryValueConfig>) {
            throw std::runtime_error("Cannot mutate QUERY_INVENTORY game value (read-only)");
          }
        },
        _config.value);
  }

private:
  GameValueMutationConfig _config;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_GAME_VALUE_MUTATION_HPP_
