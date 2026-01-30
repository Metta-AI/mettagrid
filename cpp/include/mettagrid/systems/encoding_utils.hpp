#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_SYSTEMS_ENCODING_UTILS_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_SYSTEMS_ENCODING_UTILS_HPP_

#include <vector>

#include "core/grid_object.hpp"

// Encapsulates multi-token encoding configuration and logic
class ObservationTokenEncoder {
  unsigned int _token_value_base;

public:
  explicit ObservationTokenEncoder(unsigned int base) : _token_value_base(base) {}

  // Encode a value into multiple tokens with sequential feature IDs
  std::vector<PartialObservationToken> encode(ObservationType base_feature_id, uint32_t value) const {
    std::vector<PartialObservationToken> tokens;

    uint32_t remaining = value;
    ObservationType current_feature_id = base_feature_id;

    // Base token (always emitted)
    tokens.push_back({current_feature_id, static_cast<ObservationType>(remaining % _token_value_base)});
    remaining /= _token_value_base;
    current_feature_id++;

    // Higher-order tokens (only if needed)
    while (remaining > 0) {
      tokens.push_back({current_feature_id, static_cast<ObservationType>(remaining % _token_value_base)});
      remaining /= _token_value_base;
      current_feature_id++;
    }

    return tokens;
  }

  unsigned int token_value_base() const {
    return _token_value_base;
  }
};

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_SYSTEMS_ENCODING_UTILS_HPP_
