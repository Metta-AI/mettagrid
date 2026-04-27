#include <gtest/gtest.h>

#include <algorithm>
#include <memory>
#include <random>
#include <set>
#include <vector>

#include "core/grid.hpp"
#include "core/grid_object.hpp"
#include "core/vision.hpp"
#include "systems/packed_coordinate.hpp"

using PackedCoordinate::ObservationPattern;
using Offset = std::pair<int, int>;

int manhattan_distance(const Offset& offset) {
  return std::abs(offset.first) + std::abs(offset.second);
}

std::vector<std::pair<int, int>> compute_sorted_offsets(int height, int width) {
  const int row_min = -height / 2;
  const int row_max = height / 2;
  const int col_min = -width / 2;
  const int col_max = width / 2;

  std::vector<std::pair<int, int>> result;

  for (int dr = row_min; dr <= row_max; ++dr) {
    for (int dc = col_min; dc <= col_max; ++dc) {
      result.emplace_back(dr, dc);
    }
  }

  std::sort(result.begin(), result.end(), [](auto a, auto b) {
    int da = std::abs(a.first) + std::abs(a.second);
    int db = std::abs(b.first) + std::abs(b.second);
    if (da != db) return da < db;
    // Optional: stable tie-breaker
    return a < b;
  });

  return result;
}

TEST(ObservationPatternTest, OffsetsWithinBounds) {
  int height = 3;
  int width = 5;
  int row_min = -height / 2;
  int row_max = height / 2;
  int col_min = -width / 2;
  int col_max = width / 2;

  for (const auto& [dr, dc] : ObservationPattern{height, width}) {
    EXPECT_GE(dr, row_min);
    EXPECT_LE(dr, row_max);
    EXPECT_GE(dc, col_min);
    EXPECT_LE(dc, col_max);
  }
}

TEST(ObservationPatternTest, OffsetsAreUnique) {
  int height = 3;
  int width = 5;
  std::set<Offset> seen;

  for (const auto& offset : ObservationPattern{height, width}) {
    EXPECT_TRUE(seen.insert(offset).second) << "Duplicate offset: (" << offset.first << "," << offset.second << ")";
  }

  EXPECT_EQ(seen.size(), height * width);
}

TEST(ObservationPatternTest, OffsetsInManhattanOrder) {
  int height = 5;
  int width = 5;
  std::vector<int> distances;

  for (const auto& offset : ObservationPattern{height, width}) {
    distances.push_back(manhattan_distance(offset));
  }

  for (size_t i = 1; i < distances.size(); ++i) {
    EXPECT_LE(distances[i - 1], distances[i]) << "Offsets not in Manhattan order at index " << i;
  }
}

namespace vision_test {

class SimpleObject : public GridObject {};

std::unique_ptr<Grid> make_grid(int h, int w) {
  return std::make_unique<Grid>(static_cast<GridCoord>(h), static_cast<GridCoord>(w));
}

void place(Grid& g, int r, int c, bool blocks_vision) {
  auto* obj = new SimpleObject();
  std::vector<int> tags;
  obj->init(1, "obj", GridLocation(static_cast<GridCoord>(r), static_cast<GridCoord>(c)), tags);
  obj->blocks_vision = blocks_vision;
  g.add_object(obj);
}

bool visible(const std::vector<uint8_t>& bm, int obs_h, int obs_w, int dr, int dc) {
  int rr = dr + obs_h / 2;
  int cc = dc + obs_w / 2;
  return bm[static_cast<size_t>(rr) * static_cast<size_t>(obs_w) + static_cast<size_t>(cc)] != 0;
}

std::vector<uint8_t> compute_bitmap(const Grid& g, int observer_row, int observer_col, int obs_h, int obs_w) {
  mettagrid::ShadowTable shadows(static_cast<ObservationCoord>(obs_h), static_cast<ObservationCoord>(obs_w));
  std::vector<uint8_t> bm;
  mettagrid::compute_visibility_bitmap(
      g, static_cast<GridCoord>(observer_row), static_cast<GridCoord>(observer_col), shadows, bm);
  return bm;
}

}  // namespace vision_test

TEST(VisibilityBitmap, EmptyGridAllVisible) {
  auto g = vision_test::make_grid(10, 10);
  const int H = 5, W = 5;
  auto bm = vision_test::compute_bitmap(*g, 5, 5, H, W);

  for (int dr = -H / 2; dr <= H / 2; ++dr) {
    for (int dc = -W / 2; dc <= W / 2; ++dc) {
      EXPECT_TRUE(vision_test::visible(bm, H, W, dr, dc)) << "expected visible at (" << dr << "," << dc << ")";
    }
  }
}

TEST(VisibilityBitmap, WallBlocksBehind) {
  // Observer at (5,5), wall at (5,7), probe at (5,9).
  auto g = vision_test::make_grid(11, 11);
  vision_test::place(*g, 5, 7, /*blocks_vision=*/true);

  const int H = 7, W = 7;
  auto bm = vision_test::compute_bitmap(*g, 5, 5, H, W);

  // Wall itself visible.
  EXPECT_TRUE(vision_test::visible(bm, H, W, 0, 2));
  // Cell directly behind wall (in rectangle range) hidden.
  EXPECT_FALSE(vision_test::visible(bm, H, W, 0, 3));
  // Cells in other directions unaffected.
  EXPECT_TRUE(vision_test::visible(bm, H, W, 0, -3));
  EXPECT_TRUE(vision_test::visible(bm, H, W, -3, 0));
  EXPECT_TRUE(vision_test::visible(bm, H, W, 3, 0));
  // Observer's own cell always visible.
  EXPECT_TRUE(vision_test::visible(bm, H, W, 0, 0));
}

TEST(VisibilityBitmap, WallRowWithGapFormsCone) {
  // Row of walls at r=6 spanning c=3..7 except c=5 (gap).
  auto g = vision_test::make_grid(11, 11);
  for (int c = 3; c <= 7; ++c) {
    if (c == 5) continue;
    vision_test::place(*g, 6, c, /*blocks_vision=*/true);
  }

  const int H = 9, W = 9;
  auto bm = vision_test::compute_bitmap(*g, 5, 5, H, W);

  // Directly below (through the gap at (6,5)) remains visible.
  EXPECT_TRUE(vision_test::visible(bm, H, W, 2, 0));
  EXPECT_TRUE(vision_test::visible(bm, H, W, 3, 0));
  // Cells behind walls (not in-line with the gap) are blocked.
  EXPECT_FALSE(vision_test::visible(bm, H, W, 2, 2));
  EXPECT_FALSE(vision_test::visible(bm, H, W, 2, -2));
}

TEST(VisibilityBitmap, CornerWallsBlockDiagonal) {
  // Observer at (5,5) with walls at (5,6) and (6,5): diagonal vision through
  // the (6,6) corner should be blocked by supercover semantics (either
  // orthogonal cell on the ray is a blocker).
  auto g = vision_test::make_grid(11, 11);
  vision_test::place(*g, 5, 6, /*blocks_vision=*/true);
  vision_test::place(*g, 6, 5, /*blocks_vision=*/true);

  const int H = 7, W = 7;
  auto bm = vision_test::compute_bitmap(*g, 5, 5, H, W);

  // Walls themselves visible.
  EXPECT_TRUE(vision_test::visible(bm, H, W, 0, 1));
  EXPECT_TRUE(vision_test::visible(bm, H, W, 1, 0));
  // Diagonal cells past the corner are hidden.
  EXPECT_FALSE(vision_test::visible(bm, H, W, 2, 2));
  EXPECT_FALSE(vision_test::visible(bm, H, W, 3, 3));
}

TEST(VisibilityBitmap, OutOfGridCellsReportVisibleByDefault) {
  // With the shadow-table design, out-of-grid cells contribute no blockers and
  // aren't in any shadow, so they're reported visible. The observation
  // emission loop still skips them via its own bounds check; the bitmap
  // contract intentionally does not depend on grid geometry.
  auto g = vision_test::make_grid(6, 6);
  const int H = 5, W = 5;
  auto bm = vision_test::compute_bitmap(*g, 1, 1, H, W);

  EXPECT_TRUE(vision_test::visible(bm, H, W, -2, -2));
  EXPECT_TRUE(vision_test::visible(bm, H, W, 0, 0));
  EXPECT_TRUE(vision_test::visible(bm, H, W, 2, 2));
}

TEST(VisibilityBitmap, SymmetryRandomized) {
  // On a random map with blockers, A sees B iff B sees A for every in-window pair.
  std::mt19937 rng(42);
  const int GRID = 20;
  const int H = 9, W = 9;
  auto g = vision_test::make_grid(GRID, GRID);
  std::bernoulli_distribution place_blocker(0.15);
  for (int r = 0; r < GRID; ++r) {
    for (int c = 0; c < GRID; ++c) {
      if (place_blocker(rng)) {
        vision_test::place(*g, r, c, /*blocks_vision=*/true);
      }
    }
  }

  std::uniform_int_distribution<int> coord(0, GRID - 1);
  for (int trial = 0; trial < 50; ++trial) {
    int ar = coord(rng), ac = coord(rng);
    int br = coord(rng), bc = coord(rng);
    int dr = br - ar, dc = bc - ac;
    if (std::abs(dr) > H / 2 || std::abs(dc) > W / 2) continue;

    auto bm_a = vision_test::compute_bitmap(*g, ar, ac, H, W);
    auto bm_b = vision_test::compute_bitmap(*g, br, bc, H, W);
    bool a_sees_b = vision_test::visible(bm_a, H, W, dr, dc);
    bool b_sees_a = vision_test::visible(bm_b, H, W, -dr, -dc);
    EXPECT_EQ(a_sees_b, b_sees_a) << "asym at (" << ar << "," << ac << ")->(" << br << "," << bc << ")";
  }
}

TEST(VisibilityBitmap, ObserverAtMapEdge) {
  // Observer at (0,0) corner. Window clips outside grid; in-grid cells still
  // report correct shadow behavior.
  auto g = vision_test::make_grid(10, 10);
  vision_test::place(*g, 0, 2, /*blocks_vision=*/true);

  const int H = 5, W = 5;
  auto bm = vision_test::compute_bitmap(*g, 0, 0, H, W);

  EXPECT_TRUE(vision_test::visible(bm, H, W, 0, 2));  // wall itself
  EXPECT_TRUE(vision_test::visible(bm, H, W, 0, 0));  // observer
}

// Direct tests for ShadowTable construction (independent of any grid).
TEST(ShadowTable, ObserverCellHasEmptyShadow) {
  mettagrid::ShadowTable shadows(5, 5);
  const size_t origin_idx = 2 * 5 + 2;  // (dr=0, dc=0)
  for (size_t c = 0; c < shadows.num_cells(); ++c) {
    EXPECT_FALSE(shadows.is_in_shadow(origin_idx, c));
  }
}

TEST(ShadowTable, AxisAlignedShadowContainsCellsBeyond) {
  mettagrid::ShadowTable shadows(7, 7);
  // Cell at (dr=0, dc=+1) — one step east of observer. A blocker there hides
  // cells whose ray from origin passes through it: all cells farther east on
  // the same row, plus any cell past it reachable via a ray that crosses
  // (0, +1) (those exist under supercover for shallow slopes). It must NOT
  // hide cells on the opposite side of the observer, orthogonal axis cells,
  // the observer itself, or the blocker cell itself.
  const int h_radius = 3, w_radius = 3;
  auto idx = [&](int dr, int dc) -> size_t {
    return static_cast<size_t>(dr + h_radius) * 7 + static_cast<size_t>(dc + w_radius);
  };

  const size_t b = idx(0, 1);
  EXPECT_FALSE(shadows.is_in_shadow(b, idx(0, 0)));   // observer
  EXPECT_FALSE(shadows.is_in_shadow(b, idx(0, 1)));   // blocker itself
  EXPECT_TRUE(shadows.is_in_shadow(b, idx(0, 2)));    // directly behind
  EXPECT_TRUE(shadows.is_in_shadow(b, idx(0, 3)));    // farther behind
  EXPECT_FALSE(shadows.is_in_shadow(b, idx(0, -1)));  // opposite direction
  EXPECT_FALSE(shadows.is_in_shadow(b, idx(0, -2)));
  EXPECT_FALSE(shadows.is_in_shadow(b, idx(1, 0)));  // orthogonal axis
  EXPECT_FALSE(shadows.is_in_shadow(b, idx(-1, 0)));
}

TEST(ShadowTable, CornerCellsShadeCellsBeyondCorner) {
  // For (0,0) → (2,2), the supercover ray visits (1,0)+(0,1), then (1,1),
  // then (2,1)+(1,2), then (2,2). So (2,2) is in the shadow of every
  // intermediate, including the corner-pair neighbors.
  mettagrid::ShadowTable shadows(7, 7);
  const int h_radius = 3, w_radius = 3;
  auto idx = [&](int dr, int dc) -> size_t {
    return static_cast<size_t>(dr + h_radius) * 7 + static_cast<size_t>(dc + w_radius);
  };
  const size_t target = idx(2, 2);

  EXPECT_TRUE(shadows.is_in_shadow(idx(1, 0), target));
  EXPECT_TRUE(shadows.is_in_shadow(idx(0, 1), target));
  EXPECT_TRUE(shadows.is_in_shadow(idx(1, 1), target));
  EXPECT_TRUE(shadows.is_in_shadow(idx(2, 1), target));
  EXPECT_TRUE(shadows.is_in_shadow(idx(1, 2), target));
  // (2,2) is the endpoint, excluded from its own shadow.
  EXPECT_FALSE(shadows.is_in_shadow(target, target));
}

TEST(ShadowTable, SymmetryAndTransposition) {
  // If the supercover ray origin → c passes through b, then by symmetry the
  // ray origin → (-c) passes through (-b). So shadow(b) and shadow(-b)
  // should be exact mirror images.
  mettagrid::ShadowTable shadows(9, 9);
  const int h_radius = 4, w_radius = 4;
  auto idx = [&](int dr, int dc) -> size_t {
    return static_cast<size_t>(dr + h_radius) * 9 + static_cast<size_t>(dc + w_radius);
  };

  for (int br = -h_radius; br <= h_radius; ++br) {
    for (int bc = -w_radius; bc <= w_radius; ++bc) {
      if (br == 0 && bc == 0) continue;
      for (int cr = -h_radius; cr <= h_radius; ++cr) {
        for (int cc = -w_radius; cc <= w_radius; ++cc) {
          bool forward = shadows.is_in_shadow(idx(br, bc), idx(cr, cc));
          bool mirrored = shadows.is_in_shadow(idx(-br, -bc), idx(-cr, -cc));
          EXPECT_EQ(forward, mirrored) << "asym shadow: b=(" << br << "," << bc << ") c=(" << cr << "," << cc << ")";
        }
      }
    }
  }
}

// Refactored to avoid parameterized test issues
TEST(ObservationPatternTest, MatchesReferenceOffsets) {
  // Test cases that were previously parameterized
  struct TestCase {
    int height;
    int width;
  };

  std::vector<TestCase> test_cases = {{3, 9}, {7, 3}, {5, 5}, {1, 1}, {1, 5}, {5, 1}};

  for (const auto& tc : test_cases) {
    SCOPED_TRACE("Height: " + std::to_string(tc.height) + ", Width: " + std::to_string(tc.width));

    auto expected = compute_sorted_offsets(tc.height, tc.width);
    std::vector<Offset> actual;
    for (const auto& offset : ObservationPattern{tc.height, tc.width}) {
      actual.push_back(offset);
    }

    EXPECT_EQ(actual, expected);
  }
}
