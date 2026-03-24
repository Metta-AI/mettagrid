#include "actions/action_handler_factory.hpp"

#include <unordered_map>

#include "actions/attack.hpp"
#include "actions/change_vibe.hpp"
#include "actions/move.hpp"
#include "actions/move_config.hpp"
#include "actions/noop.hpp"
#include "config/mettagrid_config.hpp"
#include "core/filter_config.hpp"
#include "core/mutation_config.hpp"
#include "handler/handler_config.hpp"

ActionHandlerResult create_action_handlers(const GameConfig& game_config) {
  ActionHandlerResult result;
  result.max_priority = 0;

  // Noop
  auto noop = std::make_unique<Noop>(*game_config.actions.at("noop"));
  noop->init();
  if (noop->priority > result.max_priority) result.max_priority = noop->priority;
  for (const auto& action : noop->actions()) {
    result.actions.push_back(action);
  }
  result.handlers.push_back(std::move(noop));

  // Move — build default handlers if none configured
  auto move_config = std::static_pointer_cast<const MoveActionConfig>(game_config.actions.at("move"));

  MoveActionConfig effective_move_config = *move_config;

  // Always append default handlers as fallback (custom handlers get priority by being first)
  {
    mettagrid::HandlerConfig hc("move");
    hc.filters.push_back(mettagrid::TargetLocEmptyFilterConfig{});
    hc.mutations.push_back(mettagrid::RelocateMutationConfig{});
    effective_move_config.handlers.push_back(hc);
  }
  {
    mettagrid::HandlerConfig hc("use_target");
    hc.filters.push_back(mettagrid::TargetIsUsableFilterConfig{});
    hc.mutations.push_back(mettagrid::UseTargetMutationConfig{});
    effective_move_config.handlers.push_back(hc);
  }

  auto move = std::make_unique<Move>(effective_move_config, &game_config);

  // Attack
  auto attack_config = std::static_pointer_cast<const AttackActionConfig>(game_config.actions.at("attack"));
  auto attack = std::make_unique<Attack>(*attack_config, &game_config);
  attack->init();
  if (attack->priority > result.max_priority) result.max_priority = attack->priority;
  for (const auto& action : attack->actions()) {
    result.actions.push_back(action);
  }

  move->init();
  if (move->priority > result.max_priority) result.max_priority = move->priority;
  for (const auto& action : move->actions()) {
    result.actions.push_back(action);
  }
  result.handlers.push_back(std::move(move));

  result.handlers.push_back(std::move(attack));

  // ChangeVibe
  auto change_vibe_config =
      std::static_pointer_cast<const ChangeVibeActionConfig>(game_config.actions.at("change_vibe"));
  auto change_vibe = std::make_unique<ChangeVibe>(*change_vibe_config, &game_config);
  change_vibe->init();
  if (change_vibe->priority > result.max_priority) result.max_priority = change_vibe->priority;
  for (const auto& action : change_vibe->actions()) {
    result.actions.push_back(action);
  }
  result.handlers.push_back(std::move(change_vibe));

  return result;
}
