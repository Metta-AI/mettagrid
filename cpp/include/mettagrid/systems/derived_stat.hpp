#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_SYSTEMS_DERIVED_STAT_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_SYSTEMS_DERIVED_STAT_HPP_

#include <cstdint>
#include <string>

namespace mettagrid {

enum class DerivedStatType : uint8_t {
  TagCount,      // Count objects with a tag (minus offset)
  TagInventory,  // Sum inventory across objects with a tag
  Cumulative,    // Accumulate a source stat each step
};

struct DerivedStatConfig {
  std::string name;
  DerivedStatType type = DerivedStatType::TagCount;

  // TagCount: count objects with tag_id, subtract count_offset
  // TagInventory: sum resource_id across objects with tag_id (optionally filtered by require_tag_id)
  int tag_id = -1;
  int count_offset = 0;

  // TagInventory only
  int resource_id = -1;
  int require_tag_id = -1;

  // Cumulative only
  std::string source_stat;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_SYSTEMS_DERIVED_STAT_HPP_
