#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_GAME_VALUE_CONFIG_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_GAME_VALUE_CONFIG_HPP_

#include <cstdint>
#include <memory>
#include <string>
#include <variant>
#include <vector>

namespace mettagrid {
struct QueryConfig;
}  // namespace mettagrid

enum class GameValueScope : uint8_t {
  AGENT,
  GAME
};

struct InventoryValueConfig {
  GameValueScope scope = GameValueScope::AGENT;
  uint16_t id = 0;  // resource_id
};

struct StatValueConfig {
  GameValueScope scope = GameValueScope::AGENT;
  uint16_t id = 0;  // stat_id
  bool delta = false;
  std::string stat_name;  // resolved to ID at C++ init time
};

struct ConstValueConfig {
  float value = 0.0f;
};

struct QueryInventoryValueConfig {
  uint16_t id = 0;  // resource_id
  std::shared_ptr<mettagrid::QueryConfig> query;
};

struct QueryCountValueConfig {
  std::shared_ptr<mettagrid::QueryConfig> query;
};

struct SumValueConfig;

using GameValueConfig = std::variant<InventoryValueConfig,
                                     StatValueConfig,
                                     ConstValueConfig,
                                     QueryInventoryValueConfig,
                                     QueryCountValueConfig,
                                     std::shared_ptr<SumValueConfig>>;

struct SumValueConfig {
  std::vector<GameValueConfig> values;
  std::vector<float> weights;
  bool log = false;
};

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_GAME_VALUE_CONFIG_HPP_
