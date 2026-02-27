#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_SYSTEMS_STAT_WRITER_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_SYSTEMS_STAT_WRITER_HPP_

#include <string>

#include "core/game_value_config.hpp"

namespace mettagrid {

struct StatWriterConfig {
  std::string name;
  GameValueConfig value = ConstValueConfig{};
  bool accumulate = false;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_SYSTEMS_STAT_WRITER_HPP_
