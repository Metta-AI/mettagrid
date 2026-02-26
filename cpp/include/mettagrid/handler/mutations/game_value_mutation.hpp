#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_GAME_VALUE_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_GAME_VALUE_MUTATION_HPP_

#include "core/game_value.hpp"
#include "core/game_value_config.hpp"
#include "handler/handler_config.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation.hpp"

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
    HandlerContext value_ctx = ctx;
    value_ctx.actor = ctx.resolve(_config.target);
    ResolvedGameValue target_value = resolve_game_value(_config.value, value_ctx);
    target_value.update(delta);
  }

private:
  GameValueMutationConfig _config;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_GAME_VALUE_MUTATION_HPP_
