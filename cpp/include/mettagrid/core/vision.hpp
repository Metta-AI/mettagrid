#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_VISION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_VISION_HPP_

#include <cstdint>
#include <vector>

#include "core/grid.hpp"
#include "core/types.hpp"

namespace mettagrid {

// Precomputed shadow masks for a fixed observation window.
//
// The table is a pure geometric property of (obs_height, obs_width) — it has
// no dependency on the grid or the observer's position. For every in-window
// relative cell b, shadow(b) is the set of in-window cells c whose supercover
// DDA ray from the center (observer) to c passes strictly through b. (That is:
// b is a potential occluder for c; if b is occupied by a vision-blocker, c is
// hidden.) Endpoints of each ray — the observer cell and c itself — are
// excluded from the shadow, so a blocker is still marked visible; only cells
// behind it become hidden.
//
// Cells are indexed row-major: idx(dr, dc) = (dr + h_radius) * obs_width
// + (dc + w_radius). Each shadow mask is a bitset of (obs_height * obs_width)
// bits packed into consecutive uint64_t words.
//
// Supercover semantics: when the ray passes exactly through a cell corner,
// both orthogonally-adjacent cells are on the ray, so a wall at either one
// hides every cell past the corner.
class ShadowTable {
public:
  ShadowTable() = default;
  ShadowTable(ObservationCoord obs_height, ObservationCoord obs_width);

  ObservationCoord height() const {
    return _obs_height;
  }
  ObservationCoord width() const {
    return _obs_width;
  }
  size_t num_cells() const {
    return static_cast<size_t>(_obs_height) * static_cast<size_t>(_obs_width);
  }
  size_t words_per_mask() const {
    return _words_per_mask;
  }

  // Pointer to the shadow mask words for blocker cell b_idx.
  const uint64_t* mask(size_t b_idx) const {
    return _masks.data() + b_idx * _words_per_mask;
  }

  // Test whether c_idx is in b_idx's shadow. Only used by tests; the hot path
  // ORs full masks rather than probing single bits.
  bool is_in_shadow(size_t b_idx, size_t c_idx) const {
    return (_masks[b_idx * _words_per_mask + c_idx / 64] >> (c_idx % 64)) & 1ULL;
  }

private:
  ObservationCoord _obs_height = 0;
  ObservationCoord _obs_width = 0;
  size_t _words_per_mask = 0;
  std::vector<uint64_t> _masks;  // flat: _masks[b_idx * _words_per_mask + word]
};

// Fill out_bitmap (row-major, obs_height * obs_width; one byte per cell) with
// 1 where the cell is visible from (observer_row, observer_col) and 0 where a
// vision-blocking object strictly between observer and cell hides it.
//
// Per tick: iterate the observation rectangle, look up the grid cell at each
// offset, and for every cell holding a blocker, OR its precomputed shadow
// mask into a `hidden` bitset. Final visibility is `~hidden`. Cells outside
// the grid simply miss the blocker check (no object → no contribution) and
// are not treated specially here — the observation emission loop already skips
// out-of-grid cells via its bounds check.
//
// out_bitmap is resized to shadows.num_cells().
void compute_visibility_bitmap(const Grid& grid,
                               GridCoord observer_row,
                               GridCoord observer_col,
                               const ShadowTable& shadows,
                               std::vector<uint8_t>& out_bitmap);

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_VISION_HPP_
