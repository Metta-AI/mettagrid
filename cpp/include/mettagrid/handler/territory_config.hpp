#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_TERRITORY_CONFIG_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_TERRITORY_CONFIG_HPP_

#include <vector>

#include "handler/handler_config.hpp"

namespace mettagrid {

struct TerritoryConfig {
  std::vector<int> tag_prefix_ids;
  std::vector<HandlerConfig> on_enter;
  std::vector<HandlerConfig> on_exit;
  std::vector<HandlerConfig> presence;
};

struct TerritoryControlConfig {
  int strength = 1;
  int decay = 1;
  int territory_index = -1;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_TERRITORY_CONFIG_HPP_
