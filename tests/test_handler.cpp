#include <cassert>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

#include "core/grid.hpp"
#include "core/grid_object.hpp"
#include "core/tag_index.hpp"
#include "handler/filters/filter.hpp"
#include "handler/filters/neg_filter.hpp"
#include "handler/filters/resource_filter.hpp"
#include "handler/filters/shared_tag_filter.hpp"
#include "handler/filters/vibe_filter.hpp"
#include "handler/handler.hpp"
#include "handler/handler_config.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/attack_mutation.hpp"
#include "handler/mutations/mutation.hpp"
#include "handler/mutations/resource_mutation.hpp"
#include "objects/inventory_config.hpp"

using namespace mettagrid;

// Resource names for testing
static std::vector<std::string> test_resource_names = {"health", "energy", "gold"};

// Simple GridObject subclass - GridObject now has inventory and is alignable
class TestActivationObject : public GridObject {
public:
  explicit TestActivationObject(const std::string& type = "test_object", ObservationType initial_vibe = 0)
      : GridObject(create_inventory_config()) {
    type_name = type;
    vibe = initial_vibe;
    location.r = 0;
    location.c = 0;
  }

  static InventoryConfig create_inventory_config() {
    InventoryConfig config;
    config.limit_defs.push_back(LimitDef({0}, 1000));  // health
    config.limit_defs.push_back(LimitDef({1}, 1000));  // energy
    config.limit_defs.push_back(LimitDef({2}, 1000));  // gold
    return config;
  }
};

// ============================================================================
// Filter Tests
// ============================================================================

void test_vibe_filter_matches() {
  std::cout << "Testing VibeFilter matches..." << std::endl;

  TestActivationObject actor("actor", 1);    // vibe = 1
  TestActivationObject target("target", 2);  // vibe = 2

  HandlerContext ctx;
  ctx.actor = &actor;
  ctx.target = &target;

  // Filter for target with vibe_id = 2
  VibeFilterConfig config;
  config.entity = EntityRef::target;
  config.vibe_id = 2;

  VibeFilter filter(config);
  assert(filter.passes(ctx) == true);

  std::cout << "✓ VibeFilter matches test passed" << std::endl;
}

void test_vibe_filter_no_match() {
  std::cout << "Testing VibeFilter no match..." << std::endl;

  TestActivationObject actor("actor", 1);
  TestActivationObject target("target", 3);  // vibe = 3

  HandlerContext ctx;
  ctx.actor = &actor;
  ctx.target = &target;

  // Filter for target with vibe_id = 2 (doesn't match)
  VibeFilterConfig config;
  config.entity = EntityRef::target;
  config.vibe_id = 2;

  VibeFilter filter(config);
  assert(filter.passes(ctx) == false);

  std::cout << "✓ VibeFilter no match test passed" << std::endl;
}

void test_vibe_filter_actor() {
  std::cout << "Testing VibeFilter on actor..." << std::endl;

  TestActivationObject actor("actor", 5);  // vibe = 5
  TestActivationObject target("target", 0);

  HandlerContext ctx;
  ctx.actor = &actor;
  ctx.target = &target;

  // Filter for actor with vibe_id = 5
  VibeFilterConfig config;
  config.entity = EntityRef::actor;
  config.vibe_id = 5;

  VibeFilter filter(config);
  assert(filter.passes(ctx) == true);

  std::cout << "✓ VibeFilter on actor test passed" << std::endl;
}

void test_resource_filter_passes() {
  std::cout << "Testing ResourceFilter passes..." << std::endl;

  TestActivationObject actor("actor");
  TestActivationObject target("target");
  target.inventory.update(0, 100);  // 100 health

  HandlerContext ctx;
  ctx.actor = &actor;
  ctx.target = &target;

  ResourceFilterConfig config;
  config.entity = EntityRef::target;
  config.resource_id = 0;
  config.min_amount = 50;

  ResourceFilter filter(config);
  assert(filter.passes(ctx) == true);

  std::cout << "✓ ResourceFilter passes test passed" << std::endl;
}

void test_resource_filter_fails() {
  std::cout << "Testing ResourceFilter fails..." << std::endl;

  TestActivationObject actor("actor");
  TestActivationObject target("target");
  target.inventory.update(0, 25);  // Only 25 health

  HandlerContext ctx;
  ctx.actor = &actor;
  ctx.target = &target;

  ResourceFilterConfig config;
  config.entity = EntityRef::target;
  config.resource_id = 0;
  config.min_amount = 50;  // Requires 50

  ResourceFilter filter(config);
  assert(filter.passes(ctx) == false);

  std::cout << "✓ ResourceFilter fails test passed" << std::endl;
}

void test_vibe_filter_neg() {
  std::cout << "Testing NegFilter with VibeFilter..." << std::endl;

  TestActivationObject actor("actor", 1);    // vibe = 1
  TestActivationObject target("target", 2);  // vibe = 2

  HandlerContext ctx;
  ctx.actor = &actor;
  ctx.target = &target;

  // Filter for target with vibe_id = 2 (should pass)
  VibeFilterConfig config;
  config.entity = EntityRef::target;
  config.vibe_id = 2;

  VibeFilter filter_no_neg(config);
  assert(filter_no_neg.passes(ctx) == true);

  // With NegFilter, should fail
  auto inner_filter = std::make_unique<VibeFilter>(config);
  NegFilter neg_filter(std::move(inner_filter));
  assert(neg_filter.passes(ctx) == false);

  // Filter for target with vibe_id = 3 (should fail)
  VibeFilterConfig config_wrong;
  config_wrong.entity = EntityRef::target;
  config_wrong.vibe_id = 3;
  VibeFilter filter_wrong_vibe(config_wrong);
  assert(filter_wrong_vibe.passes(ctx) == false);

  // With NegFilter, should pass
  auto inner_filter_wrong = std::make_unique<VibeFilter>(config_wrong);
  NegFilter neg_filter_wrong(std::move(inner_filter_wrong));
  assert(neg_filter_wrong.passes(ctx) == true);

  std::cout << "✓ NegFilter with VibeFilter test passed" << std::endl;
}

void test_resource_filter_neg() {
  std::cout << "Testing NegFilter with ResourceFilter..." << std::endl;

  TestActivationObject actor("actor");
  TestActivationObject target("target");
  target.inventory.update(0, 100);  // 100 health

  HandlerContext ctx;
  ctx.actor = &actor;
  ctx.target = &target;

  // Filter requiring 50 health (should pass with 100)
  ResourceFilterConfig config;
  config.entity = EntityRef::target;
  config.resource_id = 0;
  config.min_amount = 50;

  ResourceFilter filter_no_neg(config);
  assert(filter_no_neg.passes(ctx) == true);

  // With NegFilter, should fail
  auto inner_filter = std::make_unique<ResourceFilter>(config);
  NegFilter neg_filter(std::move(inner_filter));
  assert(neg_filter.passes(ctx) == false);

  // Filter requiring 150 health (should fail with 100)
  ResourceFilterConfig config_too_much;
  config_too_much.entity = EntityRef::target;
  config_too_much.resource_id = 0;
  config_too_much.min_amount = 150;
  ResourceFilter filter_too_much(config_too_much);
  assert(filter_too_much.passes(ctx) == false);

  // With NegFilter, should pass
  auto inner_filter_too_much = std::make_unique<ResourceFilter>(config_too_much);
  NegFilter neg_filter_too_much(std::move(inner_filter_too_much));
  assert(neg_filter_too_much.passes(ctx) == true);

  std::cout << "✓ NegFilter with ResourceFilter test passed" << std::endl;
}

void test_tag_filter_neg() {
  std::cout << "Testing NegFilter with TagPrefixFilter..." << std::endl;

  TestActivationObject actor("actor");
  TestActivationObject target("target");
  target.tag_bits.set(42);

  HandlerContext ctx;
  ctx.actor = &actor;
  ctx.target = &target;

  // Filter for tag 42 (should pass)
  TagPrefixFilterConfig config;
  config.entity = EntityRef::target;
  config.tag_ids = {42};

  TagPrefixFilter filter_no_neg(config);
  assert(filter_no_neg.passes(ctx) == true);

  // With NegFilter, should fail
  auto inner_filter = std::make_unique<TagPrefixFilter>(config);
  NegFilter neg_filter(std::move(inner_filter));
  assert(neg_filter.passes(ctx) == false);

  // Filter for tag 99 (should fail)
  TagPrefixFilterConfig config_wrong;
  config_wrong.entity = EntityRef::target;
  config_wrong.tag_ids = {99};
  TagPrefixFilter filter_wrong_tag(config_wrong);
  assert(filter_wrong_tag.passes(ctx) == false);

  // With NegFilter, should pass
  auto inner_filter_wrong = std::make_unique<TagPrefixFilter>(config_wrong);
  NegFilter neg_filter_wrong(std::move(inner_filter_wrong));
  assert(neg_filter_wrong.passes(ctx) == true);

  std::cout << "✓ NegFilter with TagPrefixFilter test passed" << std::endl;
}

void test_tag_filter_matches() {
  std::cout << "Testing TagPrefixFilter matches..." << std::endl;

  TestActivationObject actor("actor");
  TestActivationObject target("target");
  target.tag_bits.set(42);
  target.tag_bits.set(100);

  HandlerContext ctx;
  ctx.actor = &actor;
  ctx.target = &target;

  TagPrefixFilterConfig config;
  config.entity = EntityRef::target;
  config.tag_ids = {42};

  TagPrefixFilter filter(config);
  assert(filter.passes(ctx) == true);

  std::cout << "✓ TagPrefixFilter matches test passed" << std::endl;
}

void test_tag_filter_no_match() {
  std::cout << "Testing TagPrefixFilter no match..." << std::endl;

  TestActivationObject actor("actor");
  TestActivationObject target("target");
  target.tag_bits.set(1);
  target.tag_bits.set(2);

  HandlerContext ctx;
  ctx.actor = &actor;
  ctx.target = &target;

  TagPrefixFilterConfig config;
  config.entity = EntityRef::target;
  config.tag_ids = {42};  // Target doesn't have tag 42

  TagPrefixFilter filter(config);
  assert(filter.passes(ctx) == false);

  std::cout << "✓ TagPrefixFilter no match test passed" << std::endl;
}

void test_tag_filter_on_actor() {
  std::cout << "Testing TagPrefixFilter on actor..." << std::endl;

  TestActivationObject actor("actor");
  TestActivationObject target("target");
  actor.tag_bits.set(99);

  HandlerContext ctx;
  ctx.actor = &actor;
  ctx.target = &target;

  TagPrefixFilterConfig config;
  config.entity = EntityRef::actor;
  config.tag_ids = {99};

  TagPrefixFilter filter(config);
  assert(filter.passes(ctx) == true);

  std::cout << "✓ TagPrefixFilter on actor test passed" << std::endl;
}

// ============================================================================
// Mutation Tests
// ============================================================================

void test_resource_delta_mutation_add() {
  std::cout << "Testing ResourceDeltaMutation add..." << std::endl;

  TestActivationObject actor("actor");
  TestActivationObject target("target");
  target.inventory.update(0, 100);  // Start with 100 health

  HandlerContext ctx;
  ctx.actor = &actor;
  ctx.target = &target;

  ResourceDeltaMutationConfig config;
  config.entity = EntityRef::target;
  config.resource_id = 0;
  config.delta = 50;

  ResourceDeltaMutation mutation(config);
  mutation.apply(ctx);

  assert(target.inventory.amount(0) == 150);

  std::cout << "✓ ResourceDeltaMutation add test passed" << std::endl;
}

void test_resource_delta_mutation_subtract() {
  std::cout << "Testing ResourceDeltaMutation subtract..." << std::endl;

  TestActivationObject actor("actor");
  TestActivationObject target("target");
  target.inventory.update(0, 100);

  HandlerContext ctx;
  ctx.actor = &actor;
  ctx.target = &target;

  ResourceDeltaMutationConfig config;
  config.entity = EntityRef::target;
  config.resource_id = 0;
  config.delta = -30;

  ResourceDeltaMutation mutation(config);
  mutation.apply(ctx);

  assert(target.inventory.amount(0) == 70);

  std::cout << "✓ ResourceDeltaMutation subtract test passed" << std::endl;
}

void test_resource_transfer_mutation() {
  std::cout << "Testing ResourceTransferMutation..." << std::endl;

  TestActivationObject actor("actor");
  TestActivationObject target("target");
  actor.inventory.update(1, 100);  // Actor has 100 energy

  HandlerContext ctx;
  ctx.actor = &actor;
  ctx.target = &target;

  ResourceTransferMutationConfig config;
  config.source = EntityRef::actor;
  config.destination = EntityRef::target;
  config.resource_id = 1;
  config.amount = 40;

  ResourceTransferMutation mutation(config);
  mutation.apply(ctx);

  assert(actor.inventory.amount(1) == 60);   // 100 - 40
  assert(target.inventory.amount(1) == 40);  // 0 + 40

  std::cout << "✓ ResourceTransferMutation test passed" << std::endl;
}

void test_resource_transfer_mutation_all() {
  std::cout << "Testing ResourceTransferMutation transfer all..." << std::endl;

  TestActivationObject actor("actor");
  TestActivationObject target("target");
  actor.inventory.update(2, 75);  // Actor has 75 gold

  HandlerContext ctx;
  ctx.actor = &actor;
  ctx.target = &target;

  ResourceTransferMutationConfig config;
  config.source = EntityRef::actor;
  config.destination = EntityRef::target;
  config.resource_id = 2;
  config.amount = -1;  // Transfer all

  ResourceTransferMutation mutation(config);
  mutation.apply(ctx);

  assert(actor.inventory.amount(2) == 0);    // All transferred
  assert(target.inventory.amount(2) == 75);  // Received all

  std::cout << "✓ ResourceTransferMutation transfer all test passed" << std::endl;
}

void test_clear_inventory_mutation_specific() {
  std::cout << "Testing ClearInventoryMutation specific resource..." << std::endl;

  TestActivationObject actor("actor");
  TestActivationObject target("target");
  target.inventory.update(0, 100);  // health
  target.inventory.update(1, 50);   // energy
  target.inventory.update(2, 25);   // gold

  HandlerContext ctx;
  ctx.actor = &actor;
  ctx.target = &target;

  ClearInventoryMutationConfig config;
  config.entity = EntityRef::target;
  config.resource_ids = {1};  // Clear only energy

  ClearInventoryMutation mutation(config);
  mutation.apply(ctx);

  assert(target.inventory.amount(0) == 100);  // Unchanged
  assert(target.inventory.amount(1) == 0);    // Cleared
  assert(target.inventory.amount(2) == 25);   // Unchanged

  std::cout << "✓ ClearInventoryMutation specific resource test passed" << std::endl;
}

void test_clear_inventory_mutation_all() {
  std::cout << "Testing ClearInventoryMutation all resources..." << std::endl;

  TestActivationObject actor("actor");
  TestActivationObject target("target");
  target.inventory.update(0, 100);
  target.inventory.update(1, 50);
  target.inventory.update(2, 25);

  HandlerContext ctx;
  ctx.actor = &actor;
  ctx.target = &target;

  ClearInventoryMutationConfig config;
  config.entity = EntityRef::target;
  config.resource_ids = {};  // Empty = clear all

  ClearInventoryMutation mutation(config);
  mutation.apply(ctx);

  assert(target.inventory.amount(0) == 0);
  assert(target.inventory.amount(1) == 0);
  assert(target.inventory.amount(2) == 0);

  std::cout << "✓ ClearInventoryMutation all resources test passed" << std::endl;
}

void test_attack_mutation() {
  std::cout << "Testing AttackMutation..." << std::endl;

  TestActivationObject actor("actor");
  TestActivationObject target("target");

  actor.inventory.update(0, 10);   // Weapon power = 10
  target.inventory.update(1, 3);   // Armor = 3
  target.inventory.update(2, 50);  // Health = 50

  HandlerContext ctx;
  ctx.actor = &actor;
  ctx.target = &target;

  AttackMutationConfig config;
  config.weapon_resource = 0;
  config.armor_resource = 1;
  config.health_resource = 2;
  config.damage_multiplier_pct = 100;  // 100% = 1.0x multiplier

  AttackMutation mutation(config);
  mutation.apply(ctx);

  // Damage = (10 * 100 / 100) - 3 = 7
  // Health = 50 - 7 = 43
  assert(target.inventory.amount(2) == 43);

  std::cout << "✓ AttackMutation test passed" << std::endl;
}

// ============================================================================
// Handler Tests
// ============================================================================

void test_activation_handler_multiple_mutations() {
  std::cout << "Testing Handler multiple mutations..." << std::endl;

  TestActivationObject actor("actor");
  TestActivationObject target("target");
  actor.inventory.update(2, 100);  // Actor has gold
  target.inventory.update(0, 50);  // Target has health

  HandlerConfig handler_config("multi_mutation_handler");

  // Mutation 1: Transfer gold from actor to target
  ResourceTransferMutationConfig transfer;
  transfer.source = EntityRef::actor;
  transfer.destination = EntityRef::target;
  transfer.resource_id = 2;
  transfer.amount = 30;
  handler_config.mutations.push_back(transfer);

  // Mutation 2: Add health to target
  ResourceDeltaMutationConfig heal;
  heal.entity = EntityRef::target;
  heal.resource_id = 0;
  heal.delta = 20;
  handler_config.mutations.push_back(heal);

  Handler handler(handler_config);
  HandlerContext ctx;
  ctx.actor = &actor;
  ctx.target = &target;
  bool result = handler.try_apply(ctx);

  assert(result == true);
  assert(actor.inventory.amount(2) == 70);   // 100 - 30
  assert(target.inventory.amount(2) == 30);  // 0 + 30
  assert(target.inventory.amount(0) == 70);  // 50 + 20

  std::cout << "✓ Handler multiple mutations test passed" << std::endl;
}

void test_activation_handler_check_filters_only() {
  std::cout << "Testing Handler check_filters..." << std::endl;

  TestActivationObject actor("actor");
  TestActivationObject target("target");
  target.inventory.update(0, 100);

  HandlerConfig handler_config("test_handler");

  ResourceFilterConfig resource_filter;
  resource_filter.entity = EntityRef::target;
  resource_filter.resource_id = 0;
  resource_filter.min_amount = 50;
  handler_config.filters.push_back(resource_filter);

  ResourceDeltaMutationConfig delta_mutation;
  delta_mutation.entity = EntityRef::target;
  delta_mutation.resource_id = 0;
  delta_mutation.delta = -25;
  handler_config.mutations.push_back(delta_mutation);

  Handler handler(handler_config);

  // check_filters should pass but NOT apply mutations
  HandlerContext ctx;
  ctx.actor = &actor;
  ctx.target = &target;
  bool can_apply = handler.check_filters(ctx);
  assert(can_apply == true);
  assert(target.inventory.amount(0) == 100);  // Still unchanged

  std::cout << "✓ Handler check_filters test passed" << std::endl;
}

// ============================================================================
// Remove Source When Empty Tests
// ============================================================================

void test_resource_transfer_remove_source_when_empty() {
  std::cout << "Testing ResourceTransferMutation remove_source_when_empty..." << std::endl;

  // Create a grid and place a target object on it
  Grid grid(10, 10);
  TagIndex tag_index;

  TestActivationObject actor("actor");
  actor.location.r = 0;
  actor.location.c = 0;

  // Create target (extractor) with 10 gold, place on grid
  auto* target = new TestActivationObject("extractor");
  target->location.r = 1;
  target->location.c = 1;
  target->inventory.update(2, 10);  // 10 gold
  target->tag_bits.set(42);
  grid.add_object(target);
  tag_index.register_object(target);

  // Verify target is on grid and in tag index
  assert(grid.object_at(GridLocation(1, 1)) == target);
  assert(tag_index.count_objects_with_tag(42) == 1);

  // Transfer all gold from target to actor, with remove_source_when_empty=true
  HandlerContext ctx;
  ctx.actor = &actor;
  ctx.target = target;
  ctx.tag_index = &tag_index;
  ctx.grid = &grid;

  ResourceTransferMutationConfig config;
  config.source = EntityRef::target;
  config.destination = EntityRef::actor;
  config.resource_id = 2;
  config.amount = -1;  // Transfer all
  config.remove_source_when_empty = true;

  ResourceTransferMutation mutation(config);
  mutation.apply(ctx);

  // Gold transferred
  assert(actor.inventory.amount(2) == 10);
  assert(target->inventory.amount(2) == 0);

  // Target should be removed from grid and tag index
  assert(grid.object_at(GridLocation(1, 1)) == nullptr);
  assert(tag_index.count_objects_with_tag(42) == 0);

  std::cout << "✓ ResourceTransferMutation remove_source_when_empty test passed" << std::endl;
}

void test_resource_transfer_remove_source_not_empty_yet() {
  std::cout << "Testing ResourceTransferMutation remove_source_when_empty (not empty yet)..." << std::endl;

  Grid grid(10, 10);
  TagIndex tag_index;

  TestActivationObject actor("actor");
  actor.location.r = 0;
  actor.location.c = 0;

  auto* target = new TestActivationObject("extractor");
  target->location.r = 1;
  target->location.c = 1;
  target->inventory.update(2, 10);  // 10 gold
  grid.add_object(target);
  tag_index.register_object(target);

  HandlerContext ctx;
  ctx.actor = &actor;
  ctx.target = target;
  ctx.tag_index = &tag_index;
  ctx.grid = &grid;

  // Transfer only 5 gold - target still has 5 remaining
  ResourceTransferMutationConfig config;
  config.source = EntityRef::target;
  config.destination = EntityRef::actor;
  config.resource_id = 2;
  config.amount = 5;
  config.remove_source_when_empty = true;

  ResourceTransferMutation mutation(config);
  mutation.apply(ctx);

  assert(actor.inventory.amount(2) == 5);
  assert(target->inventory.amount(2) == 5);

  // Target should still be on grid (not empty yet)
  assert(grid.object_at(GridLocation(1, 1)) == target);

  std::cout << "✓ ResourceTransferMutation not empty yet test passed" << std::endl;
}

void test_resource_transfer_remove_source_flag_off() {
  std::cout << "Testing ResourceTransferMutation without remove flag..." << std::endl;

  Grid grid(10, 10);
  TagIndex tag_index;

  TestActivationObject actor("actor");
  actor.location.r = 0;
  actor.location.c = 0;

  auto* target = new TestActivationObject("extractor");
  target->location.r = 1;
  target->location.c = 1;
  target->inventory.update(2, 10);
  grid.add_object(target);

  HandlerContext ctx;
  ctx.actor = &actor;
  ctx.target = target;
  ctx.tag_index = &tag_index;
  ctx.grid = &grid;

  // Transfer all but without the flag
  ResourceTransferMutationConfig config;
  config.source = EntityRef::target;
  config.destination = EntityRef::actor;
  config.resource_id = 2;
  config.amount = -1;
  config.remove_source_when_empty = false;  // Flag off

  ResourceTransferMutation mutation(config);
  mutation.apply(ctx);

  assert(target->inventory.amount(2) == 0);

  // Target should still be on grid (flag is off)
  assert(grid.object_at(GridLocation(1, 1)) == target);

  std::cout << "✓ ResourceTransferMutation without remove flag test passed" << std::endl;
}

void test_resource_transfer_remove_source_multiple_resources() {
  std::cout << "Testing remove_source_when_empty with multiple resources..." << std::endl;

  Grid grid(10, 10);
  TagIndex tag_index;

  TestActivationObject actor("actor");
  actor.location.r = 0;
  actor.location.c = 0;

  auto* target = new TestActivationObject("extractor");
  target->location.r = 1;
  target->location.c = 1;
  target->inventory.update(1, 5);   // 5 energy
  target->inventory.update(2, 10);  // 10 gold
  grid.add_object(target);

  HandlerContext ctx;
  ctx.actor = &actor;
  ctx.target = target;
  ctx.tag_index = &tag_index;
  ctx.grid = &grid;

  // Transfer all gold - but target still has energy
  ResourceTransferMutationConfig config;
  config.source = EntityRef::target;
  config.destination = EntityRef::actor;
  config.resource_id = 2;
  config.amount = -1;
  config.remove_source_when_empty = true;

  ResourceTransferMutation mutation(config);
  mutation.apply(ctx);

  // Gold gone, energy remains
  assert(target->inventory.amount(2) == 0);
  assert(target->inventory.amount(1) == 5);

  // Target should still be on grid (still has energy)
  assert(grid.object_at(GridLocation(1, 1)) == target);

  std::cout << "✓ remove_source_when_empty with multiple resources test passed" << std::endl;
}

int main() {
  std::cout << "Running Handler tests..." << std::endl;
  std::cout << "================================================" << std::endl;

  // Filter tests
  test_vibe_filter_matches();
  test_vibe_filter_no_match();
  test_vibe_filter_actor();
  test_resource_filter_passes();
  test_resource_filter_fails();
  test_tag_filter_matches();
  test_tag_filter_no_match();
  test_tag_filter_on_actor();

  // Filter invert tests
  test_vibe_filter_neg();
  test_resource_filter_neg();
  test_tag_filter_neg();

  // Mutation tests
  test_resource_delta_mutation_add();
  test_resource_delta_mutation_subtract();
  test_resource_transfer_mutation();
  test_resource_transfer_mutation_all();
  test_clear_inventory_mutation_specific();
  test_clear_inventory_mutation_all();
  test_attack_mutation();

  // Handler tests
  test_activation_handler_multiple_mutations();
  test_activation_handler_check_filters_only();

  // Remove source when empty tests
  test_resource_transfer_remove_source_when_empty();
  test_resource_transfer_remove_source_not_empty_yet();
  test_resource_transfer_remove_source_flag_off();
  test_resource_transfer_remove_source_multiple_resources();

  std::cout << "================================================" << std::endl;
  std::cout << "All Handler tests passed! ✓" << std::endl;

  return 0;
}
