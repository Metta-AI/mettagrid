#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_STATS_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_STATS_MUTATION_HPP_

#include "handler/handler_config.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation.hpp"
#include "objects/agent.hpp"
#include "objects/collective.hpp"

namespace mettagrid {

/**
 * StatsMutation: Log a stat with a specified delta
 * Logs the stat to the specified stats tracker (game, agent, or collective).
 */
class StatsMutation : public Mutation {
public:
  explicit StatsMutation(const StatsMutationConfig& config) : _config(config) {}

  void apply(HandlerContext& ctx) override {
    switch (_config.target) {
      case StatsTarget::game: {
        // Log to game-level stats tracker
        if (ctx.game_stats != nullptr) {
          ctx.game_stats->add(_config.stat_name, _config.delta);
        }
        break;
      }
      case StatsTarget::agent: {
        // Log to target agent's stats tracker
        Agent* agent = dynamic_cast<Agent*>(ctx.target);
        if (agent != nullptr) {
          agent->stats.add(_config.stat_name, _config.delta);
        }
        break;
      }
      case StatsTarget::collective: {
        // Log to target's collective's stats tracker
        Collective* coll = ctx.target_collective();
        if (coll != nullptr) {
          coll->stats.add(_config.stat_name, _config.delta);
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
