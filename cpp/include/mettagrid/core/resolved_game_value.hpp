#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_RESOLVED_GAME_VALUE_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_RESOLVED_GAME_VALUE_HPP_

#include <cassert>

#include "core/game_value_config.hpp"
#include "core/tag_index.hpp"

struct ResolvedGameValue {
  bool delta = false;
  bool mutable_ = true;  // false for tag counts (read-only)
  float* value_ptr = nullptr;
  float prev_value = 0.0f;

  float read() const {
    if (value_ptr == nullptr) return 0.0f;
    float current = *value_ptr;
    if (!delta) return current;
    return current - prev_value;
  }

  // Read and consume the delta (resets baseline to current value)
  float read_delta() {
    if (value_ptr == nullptr) return 0.0f;
    float current = *value_ptr;
    float d = current - prev_value;
    prev_value = current;
    return d;
  }

  // Reset the delta baseline to the current value
  void reset_delta() {
    if (value_ptr != nullptr) {
      prev_value = *value_ptr;
    }
  }

  void write(float value) {
    assert(mutable_ && "Cannot write to a read-only ResolvedGameValue (e.g. tag count)");
    if (value_ptr != nullptr) {
      *value_ptr = value;
    }
  }
};

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_RESOLVED_GAME_VALUE_HPP_
