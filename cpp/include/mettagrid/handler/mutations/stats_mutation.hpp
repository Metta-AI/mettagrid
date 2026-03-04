#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_STATS_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_STATS_MUTATION_HPP_

#include <cassert>

#include "handler/handler_config.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation.hpp"
#include "objects/agent.hpp"

namespace mettagrid {

/**
 * StatsMutation: Set a stat to a computed value.
 * The source game value is resolved and written to the specified stats tracker (game or agent).
 */
class StatsMutation : public Mutation {
public:
  explicit StatsMutation(const StatsMutationConfig& config) : _config(config) {}

  void apply(HandlerContext& ctx) override {
    HasInventory* entity = (_config.entity == StatsEntity::actor) ? ctx.actor : ctx.target;
    EntityRef entity_ref = (_config.entity == StatsEntity::actor) ? EntityRef::actor : EntityRef::target;

    float value = ctx.resolve_game_value(_config.source, entity_ref);

    switch (_config.target) {
      case StatsTarget::game: {
        assert(ctx.game_stats != nullptr && "StatsMutation(game) requires HandlerContext.game_stats");
        ctx.game_stats->set(_config.stat_name, value);
        break;
      }
      case StatsTarget::agent: {
        Agent* agent = dynamic_cast<Agent*>(entity);
        if (agent != nullptr) {
          agent->stats.set(_config.stat_name, value);
        }
        break;
      }
    }
  }

private:
  StatsMutationConfig _config;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_STATS_MUTATION_HPP_
