#include <cassert>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

#include "core/grid.hpp"
#include "core/grid_object.hpp"
#include "core/tag_index.hpp"
#include "handler/filters/alignment_filter.hpp"
#include "handler/filters/filter.hpp"
#include "handler/filters/near_filter.hpp"
#include "handler/filters/resource_filter.hpp"
#include "handler/filters/tag_filter.hpp"
#include "handler/filters/vibe_filter.hpp"
#include "handler/handler.hpp"
#include "handler/handler_config.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/alignment_mutation.hpp"
#include "handler/mutations/attack_mutation.hpp"
#include "handler/mutations/mutation.hpp"
#include "handler/mutations/resource_mutation.hpp"
#include "objects/collective.hpp"
#include "objects/collective_config.hpp"
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

// Helper to create a collective config
CollectiveConfig create_test_collective_config(const std::string& name) {
  CollectiveConfig config;
  config.name = name;
  config.inventory_config.limit_defs.push_back(LimitDef({0}, 1000));
  config.inventory_config.limit_defs.push_back(LimitDef({1}, 1000));
  config.inventory_config.limit_defs.push_back(LimitDef({2}, 1000));
  return config;
}

// ============================================================================
// Filter Tests
// ============================================================================

void test_vibe_filter_matches() {
  std::cout << "Testing VibeFilter matches..." << std::endl;

  TestActivationObject actor("actor", 1);    // vibe = 1
  TestActivationObject target("target", 2);  // vibe = 2

  HandlerContext ctx(&actor, &target);

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

  HandlerContext ctx(&actor, &target);

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

  HandlerContext ctx(&actor, &target);

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

  HandlerContext ctx(&actor, &target);

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

  HandlerContext ctx(&actor, &target);

  ResourceFilterConfig config;
  config.entity = EntityRef::target;
  config.resource_id = 0;
  config.min_amount = 50;  // Requires 50

  ResourceFilter filter(config);
  assert(filter.passes(ctx) == false);

  std::cout << "✓ ResourceFilter fails test passed" << std::endl;
}

void test_alignment_filter_same_collective() {
  std::cout << "Testing AlignmentFilter same_collective..." << std::endl;

  CollectiveConfig coll_config = create_test_collective_config("team_a");
  Collective collective(coll_config, &test_resource_names);

  TestActivationObject actor("actor");
  TestActivationObject target("target");

  actor.setCollective(&collective);
  target.setCollective(&collective);

  HandlerContext ctx(&actor, &target);

  AlignmentFilterConfig config;
  config.condition = AlignmentCondition::same_collective;

  AlignmentFilter filter(config);
  assert(filter.passes(ctx) == true);

  std::cout << "✓ AlignmentFilter same_collective test passed" << std::endl;
}

void test_alignment_filter_different_collective() {
  std::cout << "Testing AlignmentFilter different_collective..." << std::endl;

  CollectiveConfig coll_config_a = create_test_collective_config("team_a");
  CollectiveConfig coll_config_b = create_test_collective_config("team_b");
  Collective collective_a(coll_config_a, &test_resource_names);
  Collective collective_b(coll_config_b, &test_resource_names);

  TestActivationObject actor("actor");
  TestActivationObject target("target");

  actor.setCollective(&collective_a);
  target.setCollective(&collective_b);

  HandlerContext ctx(&actor, &target);

  AlignmentFilterConfig config;
  config.condition = AlignmentCondition::different_collective;

  AlignmentFilter filter(config);
  assert(filter.passes(ctx) == true);

  std::cout << "✓ AlignmentFilter different_collective test passed" << std::endl;
}

void test_alignment_filter_unaligned() {
  std::cout << "Testing AlignmentFilter unaligned..." << std::endl;

  TestActivationObject actor("actor");
  TestActivationObject target("target");
  // Neither has a collective

  HandlerContext ctx(&actor, &target);

  AlignmentFilterConfig config;
  config.condition = AlignmentCondition::unaligned;

  AlignmentFilter filter(config);
  assert(filter.passes(ctx) == true);

  std::cout << "✓ AlignmentFilter unaligned test passed" << std::endl;
}

void test_tag_filter_matches() {
  std::cout << "Testing TagFilter matches..." << std::endl;

  TestActivationObject actor("actor");
  TestActivationObject target("target");
  target.tag_ids.insert(42);
  target.tag_ids.insert(100);

  HandlerContext ctx(&actor, &target);

  TagFilterConfig config;
  config.entity = EntityRef::target;
  config.tag_id = 42;

  TagFilter filter(config);
  assert(filter.passes(ctx) == true);

  std::cout << "✓ TagFilter matches test passed" << std::endl;
}

void test_tag_filter_no_match() {
  std::cout << "Testing TagFilter no match..." << std::endl;

  TestActivationObject actor("actor");
  TestActivationObject target("target");
  target.tag_ids.insert(1);
  target.tag_ids.insert(2);

  HandlerContext ctx(&actor, &target);

  TagFilterConfig config;
  config.entity = EntityRef::target;
  config.tag_id = 42;  // Target doesn't have tag 42

  TagFilter filter(config);
  assert(filter.passes(ctx) == false);

  std::cout << "✓ TagFilter no match test passed" << std::endl;
}

void test_tag_filter_on_actor() {
  std::cout << "Testing TagFilter on actor..." << std::endl;

  TestActivationObject actor("actor");
  TestActivationObject target("target");
  actor.tag_ids.insert(99);

  HandlerContext ctx(&actor, &target);

  TagFilterConfig config;
  config.entity = EntityRef::actor;
  config.tag_id = 99;

  TagFilter filter(config);
  assert(filter.passes(ctx) == true);

  std::cout << "✓ TagFilter on actor test passed" << std::endl;
}

// ============================================================================
// Mutation Tests
// ============================================================================

void test_resource_delta_mutation_add() {
  std::cout << "Testing ResourceDeltaMutation add..." << std::endl;

  TestActivationObject actor("actor");
  TestActivationObject target("target");
  target.inventory.update(0, 100);  // Start with 100 health

  HandlerContext ctx(&actor, &target);

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

  HandlerContext ctx(&actor, &target);

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

  HandlerContext ctx(&actor, &target);

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

  HandlerContext ctx(&actor, &target);

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

void test_alignment_mutation_to_actor_collective() {
  std::cout << "Testing AlignmentMutation to actor collective..." << std::endl;

  CollectiveConfig coll_config = create_test_collective_config("team_a");
  Collective collective(coll_config, &test_resource_names);

  TestActivationObject actor("actor");
  TestActivationObject target("target");

  actor.setCollective(&collective);
  // Target has no collective initially

  HandlerContext ctx(&actor, &target);

  AlignmentMutationConfig config;
  config.align_to = AlignTo::actor_collective;

  AlignmentMutation mutation(config);
  mutation.apply(ctx);

  assert(target.getCollective() == &collective);

  std::cout << "✓ AlignmentMutation to actor collective test passed" << std::endl;
}

void test_alignment_mutation_to_none() {
  std::cout << "Testing AlignmentMutation to none..." << std::endl;

  CollectiveConfig coll_config = create_test_collective_config("team_a");
  Collective collective(coll_config, &test_resource_names);

  TestActivationObject actor("actor");
  TestActivationObject target("target");

  target.setCollective(&collective);

  HandlerContext ctx(&actor, &target);

  AlignmentMutationConfig config;
  config.align_to = AlignTo::none;

  AlignmentMutation mutation(config);
  mutation.apply(ctx);

  assert(target.getCollective() == nullptr);

  std::cout << "✓ AlignmentMutation to none test passed" << std::endl;
}

void test_clear_inventory_mutation_specific() {
  std::cout << "Testing ClearInventoryMutation specific resource..." << std::endl;

  TestActivationObject actor("actor");
  TestActivationObject target("target");
  target.inventory.update(0, 100);  // health
  target.inventory.update(1, 50);   // energy
  target.inventory.update(2, 25);   // gold

  HandlerContext ctx(&actor, &target);

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

  HandlerContext ctx(&actor, &target);

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

  HandlerContext ctx(&actor, &target);

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

void test_activation_handler_filters_pass() {
  std::cout << "Testing Handler filters pass..." << std::endl;

  CollectiveConfig coll_config = create_test_collective_config("team_a");
  Collective collective(coll_config, &test_resource_names);

  TestActivationObject actor("actor");
  TestActivationObject target("target");
  actor.setCollective(&collective);
  target.setCollective(&collective);
  target.inventory.update(0, 100);

  // Create handler config with alignment and resource filters
  HandlerConfig handler_config("test_handler");

  AlignmentFilterConfig align_filter;
  align_filter.condition = AlignmentCondition::same_collective;
  handler_config.filters.push_back(align_filter);

  ResourceFilterConfig resource_filter;
  resource_filter.entity = EntityRef::target;
  resource_filter.resource_id = 0;
  resource_filter.min_amount = 50;
  handler_config.filters.push_back(resource_filter);

  // Add a mutation
  ResourceDeltaMutationConfig delta_mutation;
  delta_mutation.entity = EntityRef::target;
  delta_mutation.resource_id = 0;
  delta_mutation.delta = -25;
  handler_config.mutations.push_back(delta_mutation);

  Handler handler(handler_config);
  bool result = handler.try_apply(&actor, &target);

  assert(result == true);
  assert(target.inventory.amount(0) == 75);  // 100 - 25

  std::cout << "✓ Handler filters pass test passed" << std::endl;
}

void test_activation_handler_filters_fail() {
  std::cout << "Testing Handler filters fail..." << std::endl;

  CollectiveConfig coll_config_a = create_test_collective_config("team_a");
  CollectiveConfig coll_config_b = create_test_collective_config("team_b");
  Collective collective_a(coll_config_a, &test_resource_names);
  Collective collective_b(coll_config_b, &test_resource_names);

  TestActivationObject actor("actor");
  TestActivationObject target("target");
  actor.setCollective(&collective_a);
  target.setCollective(&collective_b);  // Different collective
  target.inventory.update(0, 100);

  // Create handler config with same_collective filter
  HandlerConfig handler_config("test_handler");

  AlignmentFilterConfig align_filter;
  align_filter.condition = AlignmentCondition::same_collective;  // Will fail
  handler_config.filters.push_back(align_filter);

  ResourceDeltaMutationConfig delta_mutation;
  delta_mutation.entity = EntityRef::target;
  delta_mutation.resource_id = 0;
  delta_mutation.delta = -25;
  handler_config.mutations.push_back(delta_mutation);

  Handler handler(handler_config);
  bool result = handler.try_apply(&actor, &target);

  assert(result == false);
  assert(target.inventory.amount(0) == 100);  // Unchanged

  std::cout << "✓ Handler filters fail test passed" << std::endl;
}

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
  bool result = handler.try_apply(&actor, &target);

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
  bool can_apply = handler.check_filters(&actor, &target);
  assert(can_apply == true);
  assert(target.inventory.amount(0) == 100);  // Still unchanged

  std::cout << "✓ Handler check_filters test passed" << std::endl;
}

// ============================================================================
// NearFilter Tests
// ============================================================================

void test_near_filter_passes_when_tagged_object_within_radius() {
  std::cout << "Testing NearFilter passes when tagged object within radius..." << std::endl;

  // Create objects
  TestActivationObject actor("actor");
  TestActivationObject target("target");
  TestActivationObject nearby_junction("junction");

  // Position them: target at (0,0), nearby_junction at (1,1) - within radius 2
  target.location.r = 0;
  target.location.c = 0;
  nearby_junction.location.r = 1;
  nearby_junction.location.c = 1;

  // Add tag to the junction
  const int junction_tag = 0;
  nearby_junction.add_tag(junction_tag);

  // Create tag index and register the junction
  TagIndex tag_index;
  tag_index.on_tag_added(&nearby_junction, junction_tag);

  // Create NearFilter that checks if target is near something with junction_tag
  NearFilterConfig config;
  config.entity = EntityRef::target;
  config.radius = 2;
  config.target_tag = junction_tag;

  NearFilter near_filter(config);

  // Create context with tag_index
  HandlerContext ctx(&actor, &target, nullptr, &tag_index);

  // Should pass - target is within radius of junction
  bool result = near_filter.passes(ctx);
  assert(result == true);

  std::cout << "✓ NearFilter passes when tagged object within radius" << std::endl;
}

void test_near_filter_fails_when_tagged_object_outside_radius() {
  std::cout << "Testing NearFilter fails when tagged object outside radius..." << std::endl;

  // Create objects
  TestActivationObject actor("actor");
  TestActivationObject target("target");
  TestActivationObject far_junction("junction");

  // Position them: target at (0,0), far_junction at (5,5) - outside radius 2
  target.location.r = 0;
  target.location.c = 0;
  far_junction.location.r = 5;
  far_junction.location.c = 5;

  // Add tag to the junction
  const int junction_tag = 0;
  far_junction.add_tag(junction_tag);

  // Create tag index and register the junction
  TagIndex tag_index;
  tag_index.on_tag_added(&far_junction, junction_tag);

  // Create NearFilter that checks if target is near something with junction_tag
  NearFilterConfig config;
  config.entity = EntityRef::target;
  config.radius = 2;
  config.target_tag = junction_tag;

  NearFilter near_filter(config);

  // Create context with tag_index
  HandlerContext ctx(&actor, &target, nullptr, &tag_index);

  // Should fail - target is outside radius of junction
  bool result = near_filter.passes(ctx);
  assert(result == false);

  std::cout << "✓ NearFilter fails when tagged object outside radius" << std::endl;
}

void test_near_filter_fails_when_no_tagged_objects() {
  std::cout << "Testing NearFilter fails when no tagged objects..." << std::endl;

  // Create objects
  TestActivationObject actor("actor");
  TestActivationObject target("target");

  target.location.r = 0;
  target.location.c = 0;

  // Create empty tag index - no objects with the tag
  const int junction_tag = 0;
  TagIndex tag_index;

  // Create NearFilter
  NearFilterConfig config;
  config.entity = EntityRef::target;
  config.radius = 2;
  config.target_tag = junction_tag;

  NearFilter near_filter(config);

  // Create context with tag_index
  HandlerContext ctx(&actor, &target, nullptr, &tag_index);

  // Should fail - no objects with the tag exist
  bool result = near_filter.passes(ctx);
  assert(result == false);

  std::cout << "✓ NearFilter fails when no tagged objects" << std::endl;
}

void test_near_filter_requires_correct_tag() {
  std::cout << "Testing NearFilter requires correct tag..." << std::endl;

  // Create objects
  TestActivationObject actor("actor");
  TestActivationObject target("target");
  TestActivationObject nearby_object("other");

  // Position them within radius
  target.location.r = 0;
  target.location.c = 0;
  nearby_object.location.r = 1;
  nearby_object.location.c = 1;

  // Add a different tag to nearby_object
  const int wrong_tag = 1;
  const int expected_tag = 0;
  nearby_object.add_tag(wrong_tag);

  // Create tag index and register with wrong tag
  TagIndex tag_index;
  tag_index.on_tag_added(&nearby_object, wrong_tag);

  // Create NearFilter looking for expected_tag
  NearFilterConfig config;
  config.entity = EntityRef::target;
  config.radius = 2;
  config.target_tag = expected_tag;

  NearFilter near_filter(config);

  // Create context with tag_index
  HandlerContext ctx(&actor, &target, nullptr, &tag_index);

  // Should fail - nearby object has wrong tag
  bool result = near_filter.passes(ctx);
  assert(result == false);

  std::cout << "✓ NearFilter requires correct tag" << std::endl;
}

void test_near_filter_evaluates_inner_filters() {
  std::cout << "Testing NearFilter evaluates inner filters..." << std::endl;

  // Create objects
  TestActivationObject actor("actor");
  TestActivationObject target("target");
  TestActivationObject nearby_junction("junction");

  // Create two collectives
  auto coll_config_a = create_test_collective_config("TeamA");
  auto coll_config_b = create_test_collective_config("TeamB");
  Collective collective_a(coll_config_a, &test_resource_names);
  Collective collective_b(coll_config_b, &test_resource_names);

  // Actor is in TeamA, nearby_junction is in TeamB
  actor.setCollective(&collective_a);
  nearby_junction.setCollective(&collective_b);

  // Position them: target at (0,0), nearby_junction at (1,1) - within radius 2
  target.location.r = 0;
  target.location.c = 0;
  nearby_junction.location.r = 1;
  nearby_junction.location.c = 1;

  // Add tag to the junction
  const int junction_tag = 0;
  nearby_junction.add_tag(junction_tag);

  // Create tag index and register the junction
  TagIndex tag_index;
  tag_index.on_tag_added(&nearby_junction, junction_tag);

  // Create NearFilter that checks if target is near something with junction_tag
  // AND that passes the inner alignment filter (same_collective as actor)
  NearFilterConfig near_config;
  near_config.entity = EntityRef::target;
  near_config.radius = 2;
  near_config.target_tag = junction_tag;

  // Create an inner alignment filter: check if candidate is in same collective as actor
  AlignmentFilterConfig align_config;
  align_config.entity = EntityRef::target;  // Will be checked against candidate in inner context
  align_config.condition = AlignmentCondition::same_collective;

  std::vector<std::unique_ptr<Filter>> inner_filters;
  inner_filters.push_back(std::make_unique<AlignmentFilter>(align_config));

  NearFilter near_filter(near_config, std::move(inner_filters));

  // Create context with tag_index
  HandlerContext ctx(&actor, &target, nullptr, &tag_index);

  // Should FAIL - junction is within radius and has the tag,
  // but it's NOT in the same collective as actor
  bool result = near_filter.passes(ctx);
  assert(result == false);

  std::cout << "✓ NearFilter evaluates inner filters" << std::endl;
}

void test_near_filter_passes_with_inner_filters() {
  std::cout << "Testing NearFilter passes when inner filters match..." << std::endl;

  // Create objects
  TestActivationObject actor("actor");
  TestActivationObject target("target");
  TestActivationObject nearby_junction("junction");

  // Create collective and put both actor and junction in it
  auto coll_config = create_test_collective_config("TeamA");
  Collective collective_a(coll_config, &test_resource_names);
  actor.setCollective(&collective_a);
  nearby_junction.setCollective(&collective_a);

  // Position them: target at (0,0), nearby_junction at (1,1) - within radius 2
  target.location.r = 0;
  target.location.c = 0;
  nearby_junction.location.r = 1;
  nearby_junction.location.c = 1;

  // Add tag to the junction
  const int junction_tag = 0;
  nearby_junction.add_tag(junction_tag);

  // Create tag index and register the junction
  TagIndex tag_index;
  tag_index.on_tag_added(&nearby_junction, junction_tag);

  // Create NearFilter that checks if target is near something with junction_tag
  // AND that passes the inner alignment filter (same_collective as actor)
  NearFilterConfig near_config;
  near_config.entity = EntityRef::target;
  near_config.radius = 2;
  near_config.target_tag = junction_tag;

  // Create an inner alignment filter: check if candidate is in same collective as actor
  AlignmentFilterConfig align_config;
  align_config.entity = EntityRef::target;  // Will be checked against candidate in inner context
  align_config.condition = AlignmentCondition::same_collective;

  std::vector<std::unique_ptr<Filter>> inner_filters;
  inner_filters.push_back(std::make_unique<AlignmentFilter>(align_config));

  NearFilter near_filter(near_config, std::move(inner_filters));

  // Create context with tag_index
  HandlerContext ctx(&actor, &target, nullptr, &tag_index);

  // Should PASS - junction is within radius, has the tag,
  // AND is in the same collective as actor
  bool result = near_filter.passes(ctx);
  assert(result == true);

  std::cout << "✓ NearFilter passes when inner filters match" << std::endl;
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
  target->tag_ids.insert(42);
  grid.add_object(target);
  tag_index.register_object(target);

  // Verify target is on grid and in tag index
  assert(grid.object_at(GridLocation(1, 1)) == target);
  assert(tag_index.count_objects_with_tag(42) == 1);

  // Transfer all gold from target to actor, with remove_source_when_empty=true
  HandlerContext ctx(&actor, target, nullptr, &tag_index);
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

  HandlerContext ctx(&actor, target, nullptr, &tag_index);
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

  HandlerContext ctx(&actor, target, nullptr, &tag_index);
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

  HandlerContext ctx(&actor, target, nullptr, &tag_index);
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
  test_alignment_filter_same_collective();
  test_alignment_filter_different_collective();
  test_alignment_filter_unaligned();
  test_tag_filter_matches();
  test_tag_filter_no_match();
  test_tag_filter_on_actor();

  // NearFilter tests
  test_near_filter_passes_when_tagged_object_within_radius();
  test_near_filter_fails_when_tagged_object_outside_radius();
  test_near_filter_fails_when_no_tagged_objects();
  test_near_filter_requires_correct_tag();
  test_near_filter_evaluates_inner_filters();
  test_near_filter_passes_with_inner_filters();

  // Mutation tests
  test_resource_delta_mutation_add();
  test_resource_delta_mutation_subtract();
  test_resource_transfer_mutation();
  test_resource_transfer_mutation_all();
  test_alignment_mutation_to_actor_collective();
  test_alignment_mutation_to_none();
  test_clear_inventory_mutation_specific();
  test_clear_inventory_mutation_all();
  test_attack_mutation();

  // Handler tests
  test_activation_handler_filters_pass();
  test_activation_handler_filters_fail();
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
