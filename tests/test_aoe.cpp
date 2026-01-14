#include <cassert>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

#include "core/aoe_helper.hpp"
#include "core/grid_object.hpp"
#include "handler/handler.hpp"
#include "handler/handler_config.hpp"
#include "objects/collective.hpp"
#include "objects/collective_config.hpp"
#include "objects/inventory_config.hpp"

using namespace mettagrid;

// Resource names for testing
static std::vector<std::string> test_resource_names = {"health", "energy", "gold"};

// Simple GridObject subclass - GridObject now has inventory and is alignable
class TestAOEObject : public GridObject {
public:
  explicit TestAOEObject(const std::string& type = "test_object", GridCoord row = 0, GridCoord col = 0)
      : GridObject(create_inventory_config()) {
    type_name = type;
    location.r = row;
    location.c = col;
  }

  static InventoryConfig create_inventory_config() {
    InventoryConfig config;
    config.limit_defs.push_back(LimitDef({0}, 1000));  // health
    config.limit_defs.push_back(LimitDef({1}, 1000));  // energy
    config.limit_defs.push_back(LimitDef({2}, 1000));  // gold
    return config;
  }
};

// Helper to create a collective config
CollectiveConfig create_test_collective_config(const std::string& name) {
  CollectiveConfig config;
  config.name = name;
  config.inventory_config.limit_defs.push_back(LimitDef({0}, 1000));
  config.inventory_config.limit_defs.push_back(LimitDef({1}, 1000));
  config.inventory_config.limit_defs.push_back(LimitDef({2}, 1000));
  return config;
}

// Helper to create an AOE handler with resource delta
std::shared_ptr<Handler> create_aoe_handler(int radius, InventoryItem resource_id, InventoryDelta delta) {
  HandlerConfig config("test_aoe");
  config.radius = radius;
  ResourceDeltaMutationConfig mutation;
  mutation.entity = EntityRef::target;
  mutation.resource_id = resource_id;
  mutation.delta = delta;
  config.mutations.push_back(mutation);
  return std::make_shared<Handler>(config);
}

// Helper to create an AOE handler with alignment filter
std::shared_ptr<Handler> create_aoe_handler_with_alignment(int radius,
                                                           InventoryItem resource_id,
                                                           InventoryDelta delta,
                                                           AlignmentCondition condition) {
  HandlerConfig config("test_aoe_aligned");
  config.radius = radius;
  AlignmentFilterConfig filter;
  filter.condition = condition;
  config.filters.push_back(filter);
  ResourceDeltaMutationConfig mutation;
  mutation.entity = EntityRef::target;
  mutation.resource_id = resource_id;
  mutation.delta = delta;
  config.mutations.push_back(mutation);
  return std::make_shared<Handler>(config);
}

// Helper to create an AOE handler with tag filter
std::shared_ptr<Handler> create_aoe_handler_with_tags(int radius,
                                                      InventoryItem resource_id,
                                                      InventoryDelta delta,
                                                      const std::vector<int>& required_tag_ids) {
  HandlerConfig config("test_aoe_tagged");
  config.radius = radius;
  TagFilterConfig filter;
  filter.entity = EntityRef::target;
  filter.required_tag_ids = required_tag_ids;
  config.filters.push_back(filter);
  ResourceDeltaMutationConfig mutation;
  mutation.entity = EntityRef::target;
  mutation.resource_id = resource_id;
  mutation.delta = delta;
  config.mutations.push_back(mutation);
  return std::make_shared<Handler>(config);
}

void test_aoe_effect_grid_creation() {
  std::cout << "Testing AOEEffectGrid creation..." << std::endl;

  AOEEffectGrid grid(10, 10);

  // No effects should be registered initially
  GridLocation loc(5, 5);
  assert(grid.effect_count_at(loc) == 0);

  std::cout << "✓ AOEEffectGrid creation test passed" << std::endl;
}

void test_register_source_basic() {
  std::cout << "Testing register_source basic..." << std::endl;

  AOEEffectGrid grid(10, 10);

  // Create a source object at position (5, 5)
  TestAOEObject source("healer", 5, 5);

  // Create a handler with radius 1 and +10 health
  auto handler = create_aoe_handler(1, 0, 10);

  grid.register_source(source, handler);

  // Effect should be registered at source location and all cells within L-infinity distance 1
  // Cells affected: all 9 cells in the 3x3 square centered at (5,5)
  assert(grid.effect_count_at(GridLocation(5, 5)) == 1);
  assert(grid.effect_count_at(GridLocation(4, 5)) == 1);
  assert(grid.effect_count_at(GridLocation(6, 5)) == 1);
  assert(grid.effect_count_at(GridLocation(5, 4)) == 1);
  assert(grid.effect_count_at(GridLocation(5, 6)) == 1);

  // Diagonal cells ARE affected with L-infinity distance
  assert(grid.effect_count_at(GridLocation(4, 4)) == 1);
  assert(grid.effect_count_at(GridLocation(4, 6)) == 1);
  assert(grid.effect_count_at(GridLocation(6, 4)) == 1);
  assert(grid.effect_count_at(GridLocation(6, 6)) == 1);

  // Cells at distance 2 should NOT be affected
  assert(grid.effect_count_at(GridLocation(3, 5)) == 0);
  assert(grid.effect_count_at(GridLocation(7, 5)) == 0);

  std::cout << "✓ register_source basic test passed" << std::endl;
}

void test_register_source_range_2() {
  std::cout << "Testing register_source with range 2..." << std::endl;

  AOEEffectGrid grid(10, 10);

  TestAOEObject source("healer", 5, 5);
  auto handler = create_aoe_handler(2, 0, 10);

  grid.register_source(source, handler);

  // Cells at distance 2 should be affected
  assert(grid.effect_count_at(GridLocation(3, 5)) == 1);
  assert(grid.effect_count_at(GridLocation(7, 5)) == 1);
  assert(grid.effect_count_at(GridLocation(5, 3)) == 1);
  assert(grid.effect_count_at(GridLocation(5, 7)) == 1);

  // Cells at distance 3 should NOT be affected
  assert(grid.effect_count_at(GridLocation(2, 5)) == 0);

  std::cout << "✓ register_source range 2 test passed" << std::endl;
}

void test_unregister_source() {
  std::cout << "Testing unregister_source..." << std::endl;

  AOEEffectGrid grid(10, 10);

  TestAOEObject source("healer", 5, 5);
  auto handler = create_aoe_handler(1, 0, 10);

  grid.register_source(source, handler);
  assert(grid.effect_count_at(GridLocation(5, 5)) == 1);

  grid.unregister_source(source);
  assert(grid.effect_count_at(GridLocation(5, 5)) == 0);
  assert(grid.effect_count_at(GridLocation(4, 5)) == 0);

  std::cout << "✓ unregister_source test passed" << std::endl;
}

void test_multiple_sources() {
  std::cout << "Testing multiple sources..." << std::endl;

  AOEEffectGrid grid(10, 10);

  TestAOEObject source1("healer1", 5, 5);
  TestAOEObject source2("healer2", 5, 6);

  auto handler1 = create_aoe_handler(1, 0, 10);
  auto handler2 = create_aoe_handler(1, 0, 5);

  grid.register_source(source1, handler1);
  grid.register_source(source2, handler2);

  // Cell (5,5) is covered by source1 only
  assert(grid.effect_count_at(GridLocation(5, 5)) == 2);  // Both sources overlap at (5,6) distance

  // Cell (5,6) is covered by both sources
  assert(grid.effect_count_at(GridLocation(5, 6)) == 2);

  // Cell (5,7) is covered by source2 only
  assert(grid.effect_count_at(GridLocation(5, 7)) == 1);

  std::cout << "✓ multiple sources test passed" << std::endl;
}

void test_apply_effects_basic() {
  std::cout << "Testing apply_effects basic..." << std::endl;

  AOEEffectGrid grid(10, 10);

  TestAOEObject source("healer", 5, 5);
  TestAOEObject target("agent", 5, 6);

  target.inventory.update(0, 100);  // Start with 100 health

  auto handler = create_aoe_handler(1, 0, 10);  // +10 health

  grid.register_source(source, handler);
  grid.apply_effects_at(target.location, target);

  // Target should have gained 10 health
  assert(target.inventory.amount(0) == 110);

  std::cout << "✓ apply_effects basic test passed" << std::endl;
}

void test_source_does_not_affect_itself() {
  std::cout << "Testing source does not affect itself..." << std::endl;

  AOEEffectGrid grid(10, 10);

  TestAOEObject source("healer", 5, 5);
  source.inventory.update(0, 100);

  auto handler = create_aoe_handler(1, 0, 10);

  grid.register_source(source, handler);
  grid.apply_effects_at(source.location, source);

  // Source should NOT be affected by its own AOE
  assert(source.inventory.amount(0) == 100);

  std::cout << "✓ source does not affect itself test passed" << std::endl;
}

void test_multiple_deltas() {
  std::cout << "Testing multiple deltas..." << std::endl;

  AOEEffectGrid grid(10, 10);

  TestAOEObject source("healer", 5, 5);
  TestAOEObject target("agent", 5, 6);

  target.inventory.update(0, 100);  // health
  target.inventory.update(1, 50);   // energy

  // Create handler with multiple mutations
  HandlerConfig config("multi_aoe");
  config.radius = 1;
  ResourceDeltaMutationConfig mutation1;
  mutation1.entity = EntityRef::target;
  mutation1.resource_id = 0;  // health
  mutation1.delta = 10;
  ResourceDeltaMutationConfig mutation2;
  mutation2.entity = EntityRef::target;
  mutation2.resource_id = 1;  // energy
  mutation2.delta = -5;
  config.mutations.push_back(mutation1);
  config.mutations.push_back(mutation2);
  auto handler = std::make_shared<Handler>(config);

  grid.register_source(source, handler);
  grid.apply_effects_at(target.location, target);

  assert(target.inventory.amount(0) == 110);  // +10 health
  assert(target.inventory.amount(1) == 45);   // -5 energy

  std::cout << "✓ multiple deltas test passed" << std::endl;
}

void test_tag_filter() {
  std::cout << "Testing tag filter..." << std::endl;

  AOEEffectGrid grid(10, 10);

  TestAOEObject source("healer", 5, 5);
  TestAOEObject target_with_tag("ally", 5, 6);
  TestAOEObject target_without_tag("enemy", 6, 5);

  // Add tag 1 to target_with_tag
  target_with_tag.tag_ids.push_back(1);

  target_with_tag.inventory.update(0, 100);
  target_without_tag.inventory.update(0, 100);

  // Handler only affects targets with tag 1
  auto handler = create_aoe_handler_with_tags(1, 0, 10, {1});

  grid.register_source(source, handler);
  grid.apply_effects_at(target_with_tag.location, target_with_tag);
  grid.apply_effects_at(target_without_tag.location, target_without_tag);

  assert(target_with_tag.inventory.amount(0) == 110);     // Has tag, affected
  assert(target_without_tag.inventory.amount(0) == 100);  // No tag, not affected

  std::cout << "✓ tag filter test passed" << std::endl;
}

void test_alignment_filter_same_collective() {
  std::cout << "Testing alignment filter (same_collective)..." << std::endl;

  AOEEffectGrid grid(10, 10);

  CollectiveConfig coll_config = create_test_collective_config("team_a");
  Collective collective(coll_config, &test_resource_names);

  TestAOEObject source("healer", 5, 5);
  TestAOEObject target_same("agent", 5, 6);
  TestAOEObject target_different("enemy", 6, 5);

  // Both source and target_same are in the same collective
  source.setCollective(&collective);
  target_same.setCollective(&collective);

  target_same.inventory.update(0, 100);
  target_different.inventory.update(0, 100);

  auto handler = create_aoe_handler_with_alignment(1, 0, 10, AlignmentCondition::same_collective);

  grid.register_source(source, handler);
  grid.apply_effects_at(target_same.location, target_same);
  grid.apply_effects_at(target_different.location, target_different);

  assert(target_same.inventory.amount(0) == 110);       // Same collective, affected
  assert(target_different.inventory.amount(0) == 100);  // No collective, not affected

  std::cout << "✓ alignment filter (same_collective) test passed" << std::endl;
}

void test_alignment_filter_different_collective() {
  std::cout << "Testing alignment filter (different_collective)..." << std::endl;

  AOEEffectGrid grid(10, 10);

  CollectiveConfig coll_config_a = create_test_collective_config("team_a");
  CollectiveConfig coll_config_b = create_test_collective_config("team_b");
  Collective collective_a(coll_config_a, &test_resource_names);
  Collective collective_b(coll_config_b, &test_resource_names);

  TestAOEObject source("damager", 5, 5);
  TestAOEObject target_same("ally", 5, 6);
  TestAOEObject target_different("enemy", 6, 5);
  TestAOEObject target_no_collective("neutral", 4, 5);

  source.setCollective(&collective_a);
  target_same.setCollective(&collective_a);
  target_different.setCollective(&collective_b);

  target_same.inventory.update(0, 100);
  target_different.inventory.update(0, 100);
  target_no_collective.inventory.update(0, 100);

  auto handler = create_aoe_handler_with_alignment(1, 0, -10, AlignmentCondition::different_collective);

  grid.register_source(source, handler);
  grid.apply_effects_at(target_same.location, target_same);
  grid.apply_effects_at(target_different.location, target_different);
  grid.apply_effects_at(target_no_collective.location, target_no_collective);

  assert(target_same.inventory.amount(0) == 100);           // Same collective, not affected
  assert(target_different.inventory.amount(0) == 90);       // Different collective, affected
  assert(target_no_collective.inventory.amount(0) == 100);  // No collective, not affected

  std::cout << "✓ alignment filter (different_collective) test passed" << std::endl;
}

void test_boundary_effects() {
  std::cout << "Testing boundary effects..." << std::endl;

  AOEEffectGrid grid(10, 10);

  // Source at corner (0, 0)
  TestAOEObject source("healer", 0, 0);

  auto handler = create_aoe_handler(2, 0, 10);

  grid.register_source(source, handler);

  // Should be registered at valid cells only
  assert(grid.effect_count_at(GridLocation(0, 0)) == 1);
  assert(grid.effect_count_at(GridLocation(0, 1)) == 1);
  assert(grid.effect_count_at(GridLocation(1, 0)) == 1);
  assert(grid.effect_count_at(GridLocation(0, 2)) == 1);
  assert(grid.effect_count_at(GridLocation(2, 0)) == 1);
  assert(grid.effect_count_at(GridLocation(1, 1)) == 1);

  // Should not wrap around or go negative
  // These would be invalid locations anyway

  std::cout << "✓ boundary effects test passed" << std::endl;
}

void test_out_of_range_target() {
  std::cout << "Testing out of range target..." << std::endl;

  AOEEffectGrid grid(10, 10);

  TestAOEObject source("healer", 5, 5);
  TestAOEObject target("agent", 0, 0);  // Far from source

  target.inventory.update(0, 100);

  auto handler = create_aoe_handler(1, 0, 10);

  grid.register_source(source, handler);
  grid.apply_effects_at(target.location, target);

  // Target should NOT be affected (out of range)
  assert(target.inventory.amount(0) == 100);

  std::cout << "✓ out of range target test passed" << std::endl;
}

int main() {
  std::cout << "Running AOE System tests..." << std::endl;
  std::cout << "================================================" << std::endl;

  test_aoe_effect_grid_creation();
  test_register_source_basic();
  test_register_source_range_2();
  test_unregister_source();
  test_multiple_sources();
  test_apply_effects_basic();
  test_source_does_not_affect_itself();
  test_multiple_deltas();
  test_tag_filter();
  test_alignment_filter_same_collective();
  test_alignment_filter_different_collective();
  test_boundary_effects();
  test_out_of_range_target();

  std::cout << "================================================" << std::endl;
  std::cout << "All AOE System tests passed! ✓" << std::endl;

  return 0;
}
