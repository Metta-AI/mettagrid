#include "handler/handler_context.hpp"

#include "core/game_value.hpp"
#include "objects/agent.hpp"

namespace mettagrid {

float HandlerContext::resolve_game_value(const GameValueConfig& cfg, EntityRef entity_ref) const {
  GridObject* entity = resolve(entity_ref);
  HandlerContext value_ctx = *this;
  value_ctx.actor = entity;
  auto rgv = ::resolve_game_value(cfg, value_ctx);
  return rgv.read();
}

StatsTracker* HandlerContext::resolve_stats_tracker(GameValueScope scope, GridObject* entity) const {
  switch (scope) {
    case GameValueScope::AGENT: {
      Agent* agent = dynamic_cast<Agent*>(entity);
      if (agent != nullptr) return &agent->stats;
      return nullptr;
    }
    case GameValueScope::GAME:
      return game_stats;
  }
  return nullptr;
}

}  // namespace mettagrid
