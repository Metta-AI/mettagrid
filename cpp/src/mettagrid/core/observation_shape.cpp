#include "core/observation_shape.hpp"

#include <cmath>
#include <cstdint>

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

}  // namespace mettagrid
