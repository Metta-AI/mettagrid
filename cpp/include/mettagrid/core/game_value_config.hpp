#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_GAME_VALUE_CONFIG_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_GAME_VALUE_CONFIG_HPP_

#include <cstdint>
#include <memory>
#include <string>
#include <variant>

namespace mettagrid {
struct QueryConfig;
}  // namespace mettagrid

enum class GameValueScope : uint8_t {
  AGENT,
  GAME,
  COLLECTIVE
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

struct TagCountValueConfig {
  uint16_t id = 0;  // tag_id
};

struct ConstValueConfig {
  float value = 0.0f;
};

struct QueryInventoryValueConfig {
  uint16_t id = 0;  // resource_id
  std::shared_ptr<mettagrid::QueryConfig> query;
};

using GameValueConfig = std::
    variant<InventoryValueConfig, StatValueConfig, TagCountValueConfig, ConstValueConfig, QueryInventoryValueConfig>;

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_GAME_VALUE_CONFIG_HPP_
