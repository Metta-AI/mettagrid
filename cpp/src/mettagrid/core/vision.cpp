#include "core/vision.hpp"

#include <cstdlib>
#include <utility>

namespace mettagrid {

namespace {

// Append every cell the supercover DDA ray from (r0, c0) to (r1, c1) visits,
// strictly between the endpoints. Supercover semantics: when the ray passes
// through a cell corner, both orthogonally-adjacent cells count as "on the
// ray".
//
// Used to build ShadowTable. The shadow table is a geometric property of the
// observation window only — it does not depend on the grid — so the DDA here
// never checks grid bounds or blockers.
void collect_ray_intermediates(int r0, int c0, int r1, int c1, std::vector<std::pair<int, int>>& out) {
  if (r0 == r1 && c0 == c1) return;

  const int dr = r1 - r0;
  const int dc = c1 - c0;
  const int step_r = (dr > 0) - (dr < 0);
  const int step_c = (dc > 0) - (dc < 0);
  const int adr = std::abs(dr);
  const int adc = std::abs(dc);

  if (adr == 0) {
    int c = c0 + step_c;
    while (c != c1) {
      out.emplace_back(r0, c);
      c += step_c;
    }
    return;
  }
  if (adc == 0) {
    int r = r0 + step_r;
    while (r != r1) {
      out.emplace_back(r, c0);
      r += step_r;
    }
    return;
  }

  // Supercover DDA with integer-scaled t (see analogous arithmetic in the
  // original ray-blocked check: t_max_r_scaled = adc, t_max_c_scaled = adr,
  // dtr = 2*adc, dtc = 2*adr).
  int tr = adc;
  int tc = adr;
  const int dtr = 2 * adc;
  const int dtc = 2 * adr;
  int cr = r0;
  int cc = c0;

  while (true) {
    if (tr < tc) {
      cr += step_r;
      tr += dtr;
    } else if (tc < tr) {
      cc += step_c;
      tc += dtc;
    } else {
      // Corner crossing: record both orthogonal neighbors (if not the endpoint)
      // before stepping diagonally.
      const int ir = cr + step_r;
      const int jc = cc + step_c;
      if (!(ir == r1 && cc == c1)) out.emplace_back(ir, cc);
      if (!(cr == r1 && jc == c1)) out.emplace_back(cr, jc);
      cr += step_r;
      cc += step_c;
      tr += dtr;
      tc += dtc;
    }

    if (cr == r1 && cc == c1) break;
    out.emplace_back(cr, cc);
  }
}

}  // namespace

ShadowTable::ShadowTable(ObservationCoord obs_height, ObservationCoord obs_width)
    : _obs_height(obs_height), _obs_width(obs_width) {
  const size_t n = static_cast<size_t>(obs_height) * static_cast<size_t>(obs_width);
  _words_per_mask = (n + 63) / 64;
  _masks.assign(n * _words_per_mask, 0);

  const int h_radius = obs_height / 2;
  const int w_radius = obs_width / 2;

  auto cell_idx = [&](int dr, int dc) -> size_t {
    return static_cast<size_t>(dr + h_radius) * static_cast<size_t>(obs_width) + static_cast<size_t>(dc + w_radius);
  };

  std::vector<std::pair<int, int>> ray;
  ray.reserve(64);

  for (int cr = -h_radius; cr <= h_radius; ++cr) {
    for (int cc = -w_radius; cc <= w_radius; ++cc) {
      if (cr == 0 && cc == 0) continue;

      ray.clear();
      collect_ray_intermediates(0, 0, cr, cc, ray);

      const size_t c_i = cell_idx(cr, cc);
      for (const auto& [br, bc] : ray) {
        const size_t b_i = cell_idx(br, bc);
        _masks[b_i * _words_per_mask + c_i / 64] |= (1ULL << (c_i % 64));
      }
    }
  }
}

void compute_visibility_bitmap(const Grid& grid,
                               GridCoord observer_row,
                               GridCoord observer_col,
                               const ShadowTable& shadows,
                               std::vector<uint8_t>& out_bitmap) {
  const size_t n_cells = shadows.num_cells();
  const size_t n_words = shadows.words_per_mask();
  out_bitmap.assign(n_cells, 1);

  if (n_words == 0) return;

  // Accumulate OR of shadow masks for every blocker in the window.
  // n_words is tiny (≤4 for a 15×15 window), so this lives comfortably on the stack.
  std::vector<uint64_t> hidden(n_words, 0);

  const int obs_height = static_cast<int>(shadows.height());
  const int obs_width = static_cast<int>(shadows.width());
  const int h_radius = obs_height / 2;
  const int w_radius = obs_width / 2;
  const int H = static_cast<int>(grid.height);
  const int W = static_cast<int>(grid.width);
  const int obs_r0 = static_cast<int>(observer_row);
  const int obs_c0 = static_cast<int>(observer_col);

  for (int dr = -h_radius; dr <= h_radius; ++dr) {
    const int target_r = obs_r0 + dr;
    if (target_r < 0 || target_r >= H) continue;
    for (int dc = -w_radius; dc <= w_radius; ++dc) {
      const int target_c = obs_c0 + dc;
      if (target_c < 0 || target_c >= W) continue;

      GridObject* o = grid.object_at(GridLocation(static_cast<GridCoord>(target_r), static_cast<GridCoord>(target_c)));
      if (o == nullptr || !o->blocks_vision) continue;

      const size_t b_idx =
          static_cast<size_t>(dr + h_radius) * static_cast<size_t>(obs_width) + static_cast<size_t>(dc + w_radius);
      const uint64_t* mask = shadows.mask(b_idx);
      for (size_t w = 0; w < n_words; ++w) {
        hidden[w] |= mask[w];
      }
    }
  }

  for (size_t idx = 0; idx < n_cells; ++idx) {
    if ((hidden[idx / 64] >> (idx % 64)) & 1ULL) {
      out_bitmap[idx] = 0;
    }
  }
}

}  // namespace mettagrid
