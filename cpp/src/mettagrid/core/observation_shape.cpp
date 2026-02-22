#include "core/observation_shape.hpp"

#include <cmath>
#include <cstdint>

#include "systems/packed_coordinate.hpp"

namespace mettagrid {

ObservationShape make_observation_shape(ObservationType observation_height, ObservationType observation_width) {
  ObservationShape shape;
  shape.row_radius = static_cast<int>(observation_height) >> 1;
  shape.col_radius = static_cast<int>(observation_width) >> 1;
  shape.row_radius_sq = static_cast<int64_t>(shape.row_radius) * shape.row_radius;
  shape.col_radius_sq = static_cast<int64_t>(shape.col_radius) * shape.col_radius;
  return shape;
}

bool within_observation_shape(int row_offset, int col_offset, const ObservationShape& observation_shape) {
  int row_radius = observation_shape.row_radius;
  int col_radius = observation_shape.col_radius;

  if (row_radius == 0 && col_radius == 0) {
    return row_offset == 0 && col_offset == 0;
  }
  if (row_radius == 0) {
    return row_offset == 0 && std::abs(col_offset) <= col_radius;
  }
  if (col_radius == 0) {
    return col_offset == 0 && std::abs(row_offset) <= row_radius;
  }

  int64_t row_sq = static_cast<int64_t>(row_offset) * row_offset;
  int64_t col_sq = static_cast<int64_t>(col_offset) * col_offset;
  if (row_radius == col_radius) {
    int64_t radius_sq = observation_shape.row_radius_sq;
    int64_t dist_sq = row_sq + col_sq;
    if (dist_sq <= radius_sq) {
      return true;
    }
    // Expand the pure cardinal tips from 1 cell to 3 cells for radius >= 2.
    if (row_radius >= 2 && dist_sq == radius_sq + 1 &&
        (std::abs(row_offset) == row_radius || std::abs(col_offset) == col_radius)) {
      return true;
    }
    return false;
  }

  // Elliptical mask for non-square observation windows.
  return row_sq * observation_shape.col_radius_sq + col_sq * observation_shape.row_radius_sq <=
         observation_shape.row_radius_sq * observation_shape.col_radius_sq;
}

void compute_observation_offsets(ObservationType observation_height,
                                 ObservationType observation_width,
                                 std::vector<std::pair<int, int>>& observation_offsets) {
  auto observation_shape = make_observation_shape(observation_height, observation_width);
  observation_offsets.clear();
  observation_offsets.reserve(static_cast<size_t>(observation_height) * static_cast<size_t>(observation_width));
  for (const auto& offset : PackedCoordinate::ObservationPattern{observation_height, observation_width}) {
    if (!within_observation_shape(offset.first, offset.second, observation_shape)) {
      continue;
    }
    observation_offsets.push_back(offset);
  }
}

}  // namespace mettagrid
