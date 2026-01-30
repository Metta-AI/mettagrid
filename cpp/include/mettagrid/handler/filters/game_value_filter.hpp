#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_GAME_VALUE_FILTER_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_GAME_VALUE_FILTER_HPP_

#include "core/game_value_config.hpp"
#include "handler/filters/filter.hpp"
#include "handler/handler_config.hpp"
#include "handler/handler_context.hpp"

namespace mettagrid {

/**
 * GameValueFilter: Check if a game value meets a minimum threshold.
 *
 * Resolves the value at check time based on the entity reference,
 * since the entity (actor/target) changes per invocation.
 */
class GameValueFilter : public Filter {
public:
  explicit GameValueFilter(const GameValueFilterConfig& config) : _config(config) {}

  bool passes(const HandlerContext& ctx) const override {
    float value = ctx.resolve_game_value(_config.value, _config.entity);
    return value >= _config.threshold;
  }

private:
  GameValueFilterConfig _config;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_GAME_VALUE_FILTER_HPP_
