#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_GAME_VALUE_CONFIG_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_GAME_VALUE_CONFIG_HPP_

#include <cstdint>
#include <string>

enum class GameValueType : uint8_t {
  INVENTORY,
  STAT,
  TAG_COUNT
};
enum class GameValueScope : uint8_t {
  AGENT,
  COLLECTIVE,
  GAME
};

struct GameValueConfig {
  GameValueType type = GameValueType::STAT;
  GameValueScope scope = GameValueScope::AGENT;
  uint16_t id = 0;  // resource_id, stat_id, or tag_id
  bool delta = false;
  std::string stat_name;  // For STAT type: resolved to ID at C++ init time
};

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_GAME_VALUE_CONFIG_HPP_
