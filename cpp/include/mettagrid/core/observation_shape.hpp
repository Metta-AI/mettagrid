#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_OBSERVATION_SHAPE_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_OBSERVATION_SHAPE_HPP_

#include "core/types.hpp"

namespace mettagrid {

struct ObservationShape {
  int row_radius = 0;
  int col_radius = 0;
  int64_t row_radius_sq = 0;
  int64_t col_radius_sq = 0;
};

ObservationShape make_observation_shape(ObservationType observation_height, ObservationType observation_width);

bool within_observation_shape(int row_offset, int col_offset, const ObservationShape& observation_shape);

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_OBSERVATION_SHAPE_HPP_
