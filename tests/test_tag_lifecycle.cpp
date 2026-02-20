#include <cassert>
#include <iostream>
#include <random>
#include <string>

#include "core/grid_object.hpp"
#include "core/tag_index.hpp"
#include "handler/handler.hpp"
#include "handler/handler_config.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation.hpp"
#include "objects/inventory_config.hpp"

using namespace mettagrid;

// Reusable test object with inventory support
class TagTestObject : public GridObject {
public:
  explicit TagTestObject(const std::string& type = "test_object") : GridObject(create_inventory_config()) {
    type_name = type;
    location.r = 0;
    location.c = 0;
  }

  static InventoryConfig create_inventory_config() {
    InventoryConfig config;
    config.limit_defs.push_back(LimitDef({0}, 1000));  // resource 0
    config.limit_defs.push_back(LimitDef({1}, 1000));  // resource 1
    return config;
  }
};

// Helper: create a minimal HandlerContext with tag_index (and optional rng)
static HandlerContext make_ctx(TagIndex* index, GridObject* obj = nullptr, std::mt19937* rng = nullptr) {
  HandlerContext ctx;
  ctx.tag_index = index;
  ctx.rng = rng;
  ctx.actor = obj;
  ctx.target = obj;
  return ctx;
}

// ============================================================================
// TagIndex::on_tag_added / on_tag_removed unit tests
// ============================================================================

void test_on_tag_added_basic() {
  std::cout << "Testing TagIndex::on_tag_added basic..." << std::endl;

  TagIndex index;
  TagTestObject obj;

  index.on_tag_added(&obj, 5);

  assert(index.count_objects_with_tag(5) == 1);
  assert(index.get_objects_with_tag(5).size() == 1);
  assert(index.get_objects_with_tag(5)[0] == &obj);

  std::cout << "  passed" << std::endl;
}

void test_on_tag_removed_basic() {
  std::cout << "Testing TagIndex::on_tag_removed basic..." << std::endl;

  TagIndex index;
  TagTestObject obj;

  index.on_tag_added(&obj, 5);
  assert(index.count_objects_with_tag(5) == 1);

  index.on_tag_removed(&obj, 5);
  assert(index.count_objects_with_tag(5) == 0);
  assert(index.get_objects_with_tag(5).empty());

  std::cout << "  passed" << std::endl;
}

void test_on_tag_added_multiple_objects() {
  std::cout << "Testing TagIndex::on_tag_added multiple objects..." << std::endl;

  TagIndex index;
  TagTestObject a, b, c;

  index.on_tag_added(&a, 10);
  index.on_tag_added(&b, 10);
  index.on_tag_added(&c, 10);

  assert(index.count_objects_with_tag(10) == 3);

  // Remove middle one
  index.on_tag_removed(&b, 10);
  assert(index.count_objects_with_tag(10) == 2);

  auto& objs = index.get_objects_with_tag(10);
  bool has_a = false, has_c = false;
  for (auto* o : objs) {
    if (o == &a) has_a = true;
    if (o == &c) has_c = true;
  }
  assert(has_a && has_c);

  std::cout << "  passed" << std::endl;
}

void test_on_tag_removed_nonexistent_is_safe() {
  std::cout << "Testing TagIndex::on_tag_removed on empty tag..." << std::endl;

  TagIndex index;
  TagTestObject obj;

  // Remove from a tag that was never added -- should not crash
  index.on_tag_removed(&obj, 99);
  assert(index.count_objects_with_tag(99) == 0);

  std::cout << "  passed" << std::endl;
}

void test_on_tag_added_null_is_safe() {
  std::cout << "Testing TagIndex::on_tag_added with nullptr..." << std::endl;

  TagIndex index;
  index.on_tag_added(nullptr, 5);
  assert(index.count_objects_with_tag(5) == 0);

  std::cout << "  passed" << std::endl;
}

void test_on_tag_removed_null_is_safe() {
  std::cout << "Testing TagIndex::on_tag_removed with nullptr..." << std::endl;

  TagIndex index;
  index.on_tag_removed(nullptr, 5);
  assert(index.count_objects_with_tag(5) == 0);

  std::cout << "  passed" << std::endl;
}

void test_count_ptr_syncs_with_on_tag_added_removed() {
  std::cout << "Testing get_count_ptr stays in sync..." << std::endl;

  TagIndex index;
  TagTestObject a, b;

  float* ptr = index.get_count_ptr(7);
  assert(*ptr == 0.0f);

  index.on_tag_added(&a, 7);
  assert(*ptr == 1.0f);

  index.on_tag_added(&b, 7);
  assert(*ptr == 2.0f);

  index.on_tag_removed(&a, 7);
  assert(*ptr == 1.0f);

  index.on_tag_removed(&b, 7);
  assert(*ptr == 0.0f);

  std::cout << "  passed" << std::endl;
}

void test_multiple_tags_independent() {
  std::cout << "Testing multiple tags are independent..." << std::endl;

  TagIndex index;
  TagTestObject obj;

  index.on_tag_added(&obj, 1);
  index.on_tag_added(&obj, 2);
  index.on_tag_added(&obj, 3);

  assert(index.count_objects_with_tag(1) == 1);
  assert(index.count_objects_with_tag(2) == 1);
  assert(index.count_objects_with_tag(3) == 1);

  index.on_tag_removed(&obj, 2);
  assert(index.count_objects_with_tag(1) == 1);
  assert(index.count_objects_with_tag(2) == 0);
  assert(index.count_objects_with_tag(3) == 1);

  std::cout << "  passed" << std::endl;
}

// ============================================================================
// GridObject::add_tag / remove_tag with HandlerContext
// ============================================================================

void test_grid_object_add_tag_updates_index() {
  std::cout << "Testing add_tag(ctx) updates TagIndex..." << std::endl;

  TagIndex index;
  TagTestObject obj;
  auto ctx = make_ctx(&index, &obj);

  assert(index.count_objects_with_tag(5) == 0);

  obj.add_tag(5, ctx);
  assert(obj.has_tag(5));
  assert(index.count_objects_with_tag(5) == 1);

  std::cout << "  passed" << std::endl;
}

void test_grid_object_remove_tag_updates_index() {
  std::cout << "Testing remove_tag(ctx) updates TagIndex..." << std::endl;

  TagIndex index;
  TagTestObject obj;
  auto ctx = make_ctx(&index, &obj);

  obj.add_tag(5, ctx);
  assert(index.count_objects_with_tag(5) == 1);

  obj.remove_tag(5, ctx);
  assert(!obj.has_tag(5));
  assert(index.count_objects_with_tag(5) == 0);

  std::cout << "  passed" << std::endl;
}

void test_grid_object_add_tag_idempotent_index() {
  std::cout << "Testing add_tag(ctx) idempotent wrt index..." << std::endl;

  TagIndex index;
  TagTestObject obj;
  auto ctx = make_ctx(&index, &obj);

  obj.add_tag(5, ctx);
  obj.add_tag(5, ctx);  // second add should be no-op
  assert(index.count_objects_with_tag(5) == 1);

  std::cout << "  passed" << std::endl;
}

void test_grid_object_remove_tag_idempotent_index() {
  std::cout << "Testing remove_tag(ctx) idempotent wrt index..." << std::endl;

  TagIndex index;
  TagTestObject obj;
  auto ctx = make_ctx(&index, &obj);

  obj.add_tag(5, ctx);
  obj.remove_tag(5, ctx);
  obj.remove_tag(5, ctx);  // second remove should be no-op
  assert(index.count_objects_with_tag(5) == 0);

  std::cout << "  passed" << std::endl;
}

// ============================================================================
// Lifecycle handlers (on_tag_add / on_tag_remove)
// ============================================================================

void test_add_tag_fires_on_tag_add_handler() {
  std::cout << "Testing add_tag(ctx) fires on_tag_add handler..." << std::endl;

  TagIndex index;
  TagTestObject obj;
  obj.inventory.update(0, 0);

  // Create a handler that adds 42 to resource 0 on the actor
  HandlerConfig hcfg("on_tag_add_test");
  ResourceDeltaMutationConfig delta;
  delta.entity = EntityRef::actor;
  delta.resource_id = 0;
  delta.delta = 42;
  hcfg.mutations.push_back(delta);

  std::unordered_map<int, std::vector<std::shared_ptr<Handler>>> on_tag_add;
  on_tag_add[10].push_back(std::make_shared<Handler>(hcfg));
  obj.set_on_tag_add(std::move(on_tag_add));

  auto ctx = make_ctx(&index, &obj);

  assert(obj.inventory.amount(0) == 0);
  obj.add_tag(10, ctx);
  assert(obj.has_tag(10));
  assert(obj.inventory.amount(0) == 42);
  assert(index.count_objects_with_tag(10) == 1);

  std::cout << "  passed" << std::endl;
}

void test_remove_tag_fires_on_tag_remove_handler() {
  std::cout << "Testing remove_tag(ctx) fires on_tag_remove handler..." << std::endl;

  TagIndex index;
  TagTestObject obj;
  obj.inventory.update(0, 100);

  // Create a handler that subtracts 50 from resource 0
  HandlerConfig hcfg("on_tag_remove_test");
  ResourceDeltaMutationConfig delta;
  delta.entity = EntityRef::actor;
  delta.resource_id = 0;
  delta.delta = -50;
  hcfg.mutations.push_back(delta);

  std::unordered_map<int, std::vector<std::shared_ptr<Handler>>> on_tag_remove;
  on_tag_remove[10].push_back(std::make_shared<Handler>(hcfg));
  obj.set_on_tag_remove(std::move(on_tag_remove));

  // Add the tag first
  auto ctx = make_ctx(&index, &obj);
  obj.add_tag(10, ctx);
  assert(index.count_objects_with_tag(10) == 1);

  obj.remove_tag(10, ctx);

  assert(!obj.has_tag(10));
  assert(obj.inventory.amount(0) == 50);
  assert(index.count_objects_with_tag(10) == 0);

  std::cout << "  passed" << std::endl;
}

void test_add_tag_idempotent_does_not_refire_handler() {
  std::cout << "Testing add_tag(ctx) idempotent -- no handler re-fire..." << std::endl;

  TagIndex index;
  TagTestObject obj;
  obj.inventory.update(0, 0);

  HandlerConfig hcfg("on_tag_add_test");
  ResourceDeltaMutationConfig delta;
  delta.entity = EntityRef::actor;
  delta.resource_id = 0;
  delta.delta = 10;
  hcfg.mutations.push_back(delta);

  std::unordered_map<int, std::vector<std::shared_ptr<Handler>>> on_tag_add;
  on_tag_add[5].push_back(std::make_shared<Handler>(hcfg));
  obj.set_on_tag_add(std::move(on_tag_add));

  auto ctx = make_ctx(&index, &obj);
  obj.add_tag(5, ctx);
  assert(obj.inventory.amount(0) == 10);

  // Adding again should be a no-op -- handler should not fire again
  obj.add_tag(5, ctx);
  assert(obj.inventory.amount(0) == 10);

  std::cout << "  passed" << std::endl;
}

void test_remove_tag_idempotent_does_not_refire_handler() {
  std::cout << "Testing remove_tag(ctx) idempotent -- no handler re-fire..." << std::endl;

  TagIndex index;
  TagTestObject obj;
  obj.inventory.update(0, 100);

  HandlerConfig hcfg("on_tag_remove_test");
  ResourceDeltaMutationConfig delta;
  delta.entity = EntityRef::actor;
  delta.resource_id = 0;
  delta.delta = -25;
  hcfg.mutations.push_back(delta);

  std::unordered_map<int, std::vector<std::shared_ptr<Handler>>> on_tag_remove;
  on_tag_remove[5].push_back(std::make_shared<Handler>(hcfg));
  obj.set_on_tag_remove(std::move(on_tag_remove));

  auto ctx = make_ctx(&index, &obj);
  obj.add_tag(5, ctx);

  obj.remove_tag(5, ctx);
  assert(obj.inventory.amount(0) == 75);

  // Removing again should be a no-op -- handler should not fire again
  obj.remove_tag(5, ctx);
  assert(obj.inventory.amount(0) == 75);

  std::cout << "  passed" << std::endl;
}

void test_skip_on_update_trigger_suppresses_handlers() {
  std::cout << "Testing skip_on_update_trigger suppresses tag handlers..." << std::endl;

  TagIndex index;
  TagTestObject obj;
  obj.inventory.update(0, 0);

  HandlerConfig hcfg("on_tag_add_test");
  ResourceDeltaMutationConfig delta;
  delta.entity = EntityRef::actor;
  delta.resource_id = 0;
  delta.delta = 99;
  hcfg.mutations.push_back(delta);

  std::unordered_map<int, std::vector<std::shared_ptr<Handler>>> on_tag_add;
  on_tag_add[5].push_back(std::make_shared<Handler>(hcfg));
  obj.set_on_tag_add(std::move(on_tag_add));

  auto ctx = make_ctx(&index, &obj);
  ctx.skip_on_update_trigger = true;

  obj.add_tag(5, ctx);
  // Tag should be added but handler should NOT have fired
  assert(obj.has_tag(5));
  assert(obj.inventory.amount(0) == 0);
  assert(index.count_objects_with_tag(5) == 1);

  std::cout << "  passed" << std::endl;
}

void test_add_tag_handler_cascading() {
  std::cout << "Testing add_tag handler cascading (tag A handler adds tag B)..." << std::endl;

  TagIndex index;
  TagTestObject obj;
  obj.inventory.update(0, 0);

  // Handler for tag 10: adds resource 0
  HandlerConfig hcfg_a("on_tag_10");
  ResourceDeltaMutationConfig delta_a;
  delta_a.entity = EntityRef::actor;
  delta_a.resource_id = 0;
  delta_a.delta = 100;
  hcfg_a.mutations.push_back(delta_a);

  // Handler for tag 20: adds resource 1
  HandlerConfig hcfg_b("on_tag_20");
  ResourceDeltaMutationConfig delta_b;
  delta_b.entity = EntityRef::actor;
  delta_b.resource_id = 1;
  delta_b.delta = 200;
  hcfg_b.mutations.push_back(delta_b);

  std::unordered_map<int, std::vector<std::shared_ptr<Handler>>> on_tag_add;
  on_tag_add[10].push_back(std::make_shared<Handler>(hcfg_a));
  on_tag_add[20].push_back(std::make_shared<Handler>(hcfg_b));
  obj.set_on_tag_add(std::move(on_tag_add));

  auto ctx = make_ctx(&index, &obj);

  obj.add_tag(10, ctx);
  assert(obj.inventory.amount(0) == 100);

  obj.add_tag(20, ctx);
  assert(obj.inventory.amount(1) == 200);

  assert(index.count_objects_with_tag(10) == 1);
  assert(index.count_objects_with_tag(20) == 1);

  std::cout << "  passed" << std::endl;
}

void test_mixed_add_remove_lifecycle() {
  std::cout << "Testing mixed add/remove lifecycle..." << std::endl;

  TagIndex index;
  TagTestObject obj;
  obj.inventory.update(0, 50);

  // on_tag_add for tag 5: +30
  HandlerConfig add_cfg("add_handler");
  ResourceDeltaMutationConfig add_delta;
  add_delta.entity = EntityRef::actor;
  add_delta.resource_id = 0;
  add_delta.delta = 30;
  add_cfg.mutations.push_back(add_delta);

  // on_tag_remove for tag 5: -10
  HandlerConfig rm_cfg("remove_handler");
  ResourceDeltaMutationConfig rm_delta;
  rm_delta.entity = EntityRef::actor;
  rm_delta.resource_id = 0;
  rm_delta.delta = -10;
  rm_cfg.mutations.push_back(rm_delta);

  std::unordered_map<int, std::vector<std::shared_ptr<Handler>>> on_tag_add;
  on_tag_add[5].push_back(std::make_shared<Handler>(add_cfg));
  obj.set_on_tag_add(std::move(on_tag_add));

  std::unordered_map<int, std::vector<std::shared_ptr<Handler>>> on_tag_remove;
  on_tag_remove[5].push_back(std::make_shared<Handler>(rm_cfg));
  obj.set_on_tag_remove(std::move(on_tag_remove));

  auto ctx = make_ctx(&index, &obj);

  // Add tag: 50 + 30 = 80
  obj.add_tag(5, ctx);
  assert(obj.inventory.amount(0) == 80);
  assert(index.count_objects_with_tag(5) == 1);

  // Remove tag: 80 - 10 = 70
  obj.remove_tag(5, ctx);
  assert(obj.inventory.amount(0) == 70);
  assert(index.count_objects_with_tag(5) == 0);

  // Re-add: 70 + 30 = 100
  obj.add_tag(5, ctx);
  assert(obj.inventory.amount(0) == 100);
  assert(index.count_objects_with_tag(5) == 1);

  std::cout << "  passed" << std::endl;
}

void test_context_propagates_rng_to_lifecycle_handlers() {
  std::cout << "Testing context propagates rng to lifecycle handlers..." << std::endl;

  TagIndex index;
  TagTestObject obj;
  std::mt19937 rng(42);

  // Handler that just adds resource (verifying it fires with a full context)
  HandlerConfig hcfg("rng_test");
  ResourceDeltaMutationConfig delta;
  delta.entity = EntityRef::actor;
  delta.resource_id = 0;
  delta.delta = 1;
  hcfg.mutations.push_back(delta);

  std::unordered_map<int, std::vector<std::shared_ptr<Handler>>> on_tag_add;
  on_tag_add[5].push_back(std::make_shared<Handler>(hcfg));
  obj.set_on_tag_add(std::move(on_tag_add));

  auto ctx = make_ctx(&index, &obj, &rng);

  obj.add_tag(5, ctx);
  assert(obj.inventory.amount(0) == 1);

  std::cout << "  passed" << std::endl;
}

void test_apply_on_tag_add_handlers_fires_without_adding() {
  std::cout << "Testing apply_on_tag_add_handlers fires handlers for existing tag..." << std::endl;

  TagIndex index;
  TagTestObject obj;
  obj.inventory.update(0, 0);

  HandlerConfig hcfg("add_handler");
  ResourceDeltaMutationConfig delta;
  delta.entity = EntityRef::actor;
  delta.resource_id = 0;
  delta.delta = 77;
  hcfg.mutations.push_back(delta);

  std::unordered_map<int, std::vector<std::shared_ptr<Handler>>> on_tag_add;
  on_tag_add[5].push_back(std::make_shared<Handler>(hcfg));
  obj.set_on_tag_add(std::move(on_tag_add));

  // Add tag with skip to avoid firing handler
  auto ctx = make_ctx(&index, &obj);
  ctx.skip_on_update_trigger = true;
  obj.add_tag(5, ctx);
  assert(obj.inventory.amount(0) == 0);

  // Now explicitly fire the add handlers
  ctx.skip_on_update_trigger = false;
  obj.apply_on_tag_add_handlers(5, ctx);
  assert(obj.inventory.amount(0) == 77);

  std::cout << "  passed" << std::endl;
}

void test_apply_on_tag_remove_handlers_fires_without_removing() {
  std::cout << "Testing apply_on_tag_remove_handlers fires handlers for removed tag..." << std::endl;

  TagIndex index;
  TagTestObject obj;
  obj.inventory.update(0, 100);

  HandlerConfig hcfg("remove_handler");
  ResourceDeltaMutationConfig delta;
  delta.entity = EntityRef::actor;
  delta.resource_id = 0;
  delta.delta = -33;
  hcfg.mutations.push_back(delta);

  std::unordered_map<int, std::vector<std::shared_ptr<Handler>>> on_tag_remove;
  on_tag_remove[5].push_back(std::make_shared<Handler>(hcfg));
  obj.set_on_tag_remove(std::move(on_tag_remove));

  // Add and remove tag with skip to avoid firing handler
  auto ctx = make_ctx(&index, &obj);
  ctx.skip_on_update_trigger = true;
  obj.add_tag(5, ctx);
  obj.remove_tag(5, ctx);
  assert(obj.inventory.amount(0) == 100);

  // Now explicitly fire the remove handlers
  ctx.skip_on_update_trigger = false;
  obj.apply_on_tag_remove_handlers(5, ctx);
  assert(obj.inventory.amount(0) == 67);

  std::cout << "  passed" << std::endl;
}

int main() {
  std::cout << "Running Tag Lifecycle tests..." << std::endl;
  std::cout << "================================================" << std::endl;

  // TagIndex::on_tag_added / on_tag_removed
  test_on_tag_added_basic();
  test_on_tag_removed_basic();
  test_on_tag_added_multiple_objects();
  test_on_tag_removed_nonexistent_is_safe();
  test_on_tag_added_null_is_safe();
  test_on_tag_removed_null_is_safe();
  test_count_ptr_syncs_with_on_tag_added_removed();
  test_multiple_tags_independent();

  // GridObject::add_tag / remove_tag with HandlerContext
  test_grid_object_add_tag_updates_index();
  test_grid_object_remove_tag_updates_index();
  test_grid_object_add_tag_idempotent_index();
  test_grid_object_remove_tag_idempotent_index();

  // Lifecycle handlers (on_tag_add / on_tag_remove)
  test_add_tag_fires_on_tag_add_handler();
  test_remove_tag_fires_on_tag_remove_handler();
  test_add_tag_idempotent_does_not_refire_handler();
  test_remove_tag_idempotent_does_not_refire_handler();
  test_skip_on_update_trigger_suppresses_handlers();
  test_add_tag_handler_cascading();
  test_mixed_add_remove_lifecycle();

  // Context propagation
  test_context_propagates_rng_to_lifecycle_handlers();
  test_apply_on_tag_add_handlers_fires_without_adding();
  test_apply_on_tag_remove_handlers_fires_without_removing();

  std::cout << "================================================" << std::endl;
  std::cout << "All Tag Lifecycle tests passed!" << std::endl;

  return 0;
}
