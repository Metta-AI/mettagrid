#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_STATS_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_STATS_MUTATION_HPP_

#include <cassert>

#include "handler/handler_config.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation.hpp"
#include "objects/agent.hpp"

namespace mettagrid {

/**
 * StatsMutation: Log a stat with a specified delta
 * Logs the stat to the specified stats tracker (game or agent).
 */
class StatsMutation : public Mutation {
public:
  explicit StatsMutation(const StatsMutationConfig& config) : _config(config) {}

  void apply(HandlerContext& ctx) override {
    HasInventory* entity = (_config.entity == StatsEntity::actor) ? ctx.actor : ctx.target;

    switch (_config.target) {
      case StatsTarget::game: {
        assert(ctx.game_stats != nullptr && "StatsMutation(game) requires HandlerContext.game_stats");
        ctx.game_stats->add(_config.stat_name, _config.delta);
        break;
      }
      case StatsTarget::agent: {
        Agent* agent = dynamic_cast<Agent*>(entity);
        if (agent != nullptr) {
          agent->stats.add(_config.stat_name, _config.delta);
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
