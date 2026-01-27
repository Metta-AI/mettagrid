#include <gtest/gtest.h>

#include <memory>
#include <string>
#include <vector>

#include "core/aoe_tracker.hpp"
#include "core/grid_object.hpp"
#include "handler/handler_config.hpp"
#include "objects/agent.hpp"
#include "objects/agent_config.hpp"
#include "objects/collective.hpp"
#include "objects/collective_config.hpp"
#include "objects/inventory_config.hpp"

using namespace mettagrid;

// Resource names for testing
static std::vector<std::string> test_resource_names = {"health", "energy", "gold"};

// Simple GridObject subclass for testing
class TestObject : public GridObject {
public:
  explicit TestObject(const std::string& type = "test_object", GridCoord row = 0, GridCoord col = 0)
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

// Helper to create an AOEConfig with resource delta mutation
AOEConfig create_aoe_config(int radius,
                            InventoryItem resource_id,
                            InventoryDelta delta,
                            bool is_static = true,
                            bool effect_self = false) {
  AOEConfig config;
  config.radius = radius;
  config.is_static = is_static;
  config.effect_self = effect_self;

  ResourceDeltaMutationConfig mutation;
  mutation.entity = EntityRef::target;
  mutation.resource_id = resource_id;
  mutation.delta = delta;
  config.mutations.push_back(mutation);

  return config;
}

// Helper to create an AOEConfig with presence deltas
AOEConfig create_aoe_config_with_presence(int radius,
                                          InventoryItem resource_id,
                                          InventoryDelta presence_delta,
                                          bool is_static = true) {
  AOEConfig config;
  config.radius = radius;
  config.is_static = is_static;
  config.effect_self = false;

  ResourceDelta rd;
  rd.resource_id = resource_id;
  rd.delta = presence_delta;
  config.presence_deltas.push_back(rd);

  return config;
}

// Test fixture for AOETracker
class AOETrackerTest : public ::testing::Test {
protected:
  void SetUp() override {
    tracker = std::make_unique<AOETracker>(10, 10);
  }

  std::unique_ptr<AOETracker> tracker;
};

// ==================== Fixed AOE Tests ====================

TEST_F(AOETrackerTest, FixedAOECreation) {
  // Create a source object at position (5, 5)
  TestObject source("healer", 5, 5);

  // Create an AOE config with radius 1
  AOEConfig config = create_aoe_config(1, 0, 10, true, false);

  tracker->register_source(source, config);

  // Effect should be registered at all cells within L-infinity distance 1
  // 9 cells in a 3x3 square centered at (5,5)
  EXPECT_EQ(1u, tracker->fixed_effect_count_at(GridLocation(5, 5)));
  EXPECT_EQ(1u, tracker->fixed_effect_count_at(GridLocation(4, 5)));
  EXPECT_EQ(1u, tracker->fixed_effect_count_at(GridLocation(6, 5)));
  EXPECT_EQ(1u, tracker->fixed_effect_count_at(GridLocation(5, 4)));
  EXPECT_EQ(1u, tracker->fixed_effect_count_at(GridLocation(5, 6)));

  // Diagonal cells ARE affected with L-infinity distance
  EXPECT_EQ(1u, tracker->fixed_effect_count_at(GridLocation(4, 4)));
  EXPECT_EQ(1u, tracker->fixed_effect_count_at(GridLocation(4, 6)));
  EXPECT_EQ(1u, tracker->fixed_effect_count_at(GridLocation(6, 4)));
  EXPECT_EQ(1u, tracker->fixed_effect_count_at(GridLocation(6, 6)));

  // Cells at distance 2 should NOT be affected
  EXPECT_EQ(0u, tracker->fixed_effect_count_at(GridLocation(3, 5)));
  EXPECT_EQ(0u, tracker->fixed_effect_count_at(GridLocation(7, 5)));
}

TEST_F(AOETrackerTest, FixedAOEApplyMutation) {
  TestObject source("healer", 5, 5);
  TestObject target("agent", 5, 6);

  target.inventory.update(0, 100);  // Start with 100 health

  AOEConfig config = create_aoe_config(1, 0, 10, true, false);  // +10 health

  tracker->register_source(source, config);
  tracker->apply_fixed(target);

  // Target should have gained 10 health
  EXPECT_EQ(110, target.inventory.amount(0));
}

TEST_F(AOETrackerTest, FixedAOEEffectSelfFalse) {
  TestObject source("healer", 5, 5);
  source.inventory.update(0, 100);

  AOEConfig config = create_aoe_config(1, 0, 10, true, false);  // effect_self=false

  tracker->register_source(source, config);
  tracker->apply_fixed(source);

  // Source should NOT be affected by its own AOE
  EXPECT_EQ(100, source.inventory.amount(0));
}

TEST_F(AOETrackerTest, FixedAOEEffectSelfTrue) {
  TestObject source("healer", 5, 5);
  source.inventory.update(0, 100);

  AOEConfig config = create_aoe_config(1, 0, 10, true, true);  // effect_self=true

  tracker->register_source(source, config);
  tracker->apply_fixed(source);

  // Source should be affected by its own AOE
  EXPECT_EQ(110, source.inventory.amount(0));
}

TEST_F(AOETrackerTest, FixedAOEUnregister) {
  TestObject source("healer", 5, 5);

  AOEConfig config = create_aoe_config(1, 0, 10, true, false);

  tracker->register_source(source, config);
  EXPECT_EQ(1u, tracker->fixed_effect_count_at(GridLocation(5, 5)));

  tracker->unregister_source(source);
  EXPECT_EQ(0u, tracker->fixed_effect_count_at(GridLocation(5, 5)));
}

TEST_F(AOETrackerTest, FixedAOEOutOfRange) {
  TestObject source("healer", 5, 5);
  TestObject target("agent", 0, 0);  // Far from source

  target.inventory.update(0, 100);

  AOEConfig config = create_aoe_config(1, 0, 10, true, false);

  tracker->register_source(source, config);
  tracker->apply_fixed(target);

  // Target should NOT be affected (out of range)
  EXPECT_EQ(100, target.inventory.amount(0));
}

// ==================== Mobile AOE Tests ====================

TEST_F(AOETrackerTest, MobileAOERegistration) {
  TestObject source("healer", 5, 5);

  AOEConfig config = create_aoe_config(1, 0, 10, false, false);  // is_static=false

  tracker->register_source(source, config);

  // Mobile AOE should be registered as a mobile source, not in cell effects
  EXPECT_EQ(1u, tracker->mobile_source_count());
  EXPECT_EQ(0u, tracker->fixed_effect_count_at(GridLocation(5, 5)));
}

// Test fixture for mobile AOE with agents
class MobileAOETest : public ::testing::Test {
protected:
  void SetUp() override {
    tracker = std::make_unique<AOETracker>(10, 10);

    // Create agent config
    InventoryConfig inv_config;
    inv_config.limit_defs.push_back(LimitDef({0}, 1000));  // health
    inv_config.limit_defs.push_back(LimitDef({1}, 1000));  // energy

    agent_config = std::make_unique<AgentConfig>(0,          // type_id
                                                 "agent",    // type_name
                                                 0,          // group_id
                                                 "red",      // group_name
                                                 0,          // freeze_duration
                                                 0,          // initial_vibe
                                                 inv_config  // inventory_config
    );
  }

  std::unique_ptr<AOETracker> tracker;
  std::unique_ptr<AgentConfig> agent_config;
};

TEST_F(MobileAOETest, MobileAOEApplyToAgents) {
  // Create two agents adjacent to each other
  Agent agent1(5, 5, *agent_config, &test_resource_names);
  Agent agent2(5, 6, *agent_config, &test_resource_names);

  agent1.inventory.update(0, 100);
  agent2.inventory.update(0, 100);

  // Register mobile AOE on agent1
  AOEConfig config = create_aoe_config(1, 0, 10, false, false);  // is_static=false, effect_self=false
  tracker->register_source(agent1, config);

  // Apply mobile AOE
  std::vector<Agent*> agents = {&agent1, &agent2};
  tracker->apply_mobile(agents);

  // Agent1 should NOT be affected (effect_self=false)
  EXPECT_EQ(100, agent1.inventory.amount(0));

  // Agent2 should be affected (+10 health)
  EXPECT_EQ(110, agent2.inventory.amount(0));
}

TEST_F(MobileAOETest, MobileAOEEffectSelfTrue) {
  Agent agent1(5, 5, *agent_config, &test_resource_names);
  agent1.inventory.update(0, 100);

  // Register mobile AOE on agent1 with effect_self=true
  AOEConfig config = create_aoe_config(1, 0, 10, false, true);  // is_static=false, effect_self=true
  tracker->register_source(agent1, config);

  // Apply mobile AOE
  std::vector<Agent*> agents = {&agent1};
  tracker->apply_mobile(agents);

  // Agent1 should be affected by its own AOE
  EXPECT_EQ(110, agent1.inventory.amount(0));
}

TEST_F(MobileAOETest, MobileAOEOutOfRange) {
  Agent agent1(0, 0, *agent_config, &test_resource_names);
  Agent agent2(9, 9, *agent_config, &test_resource_names);  // Far from agent1

  agent2.inventory.update(0, 100);

  // Register mobile AOE on agent1
  AOEConfig config = create_aoe_config(1, 0, 10, false, false);
  tracker->register_source(agent1, config);

  // Apply mobile AOE
  std::vector<Agent*> agents = {&agent1, &agent2};
  tracker->apply_mobile(agents);

  // Agent2 should NOT be affected (out of range)
  EXPECT_EQ(100, agent2.inventory.amount(0));
}

TEST_F(MobileAOETest, MobileAOEMutualEffect) {
  // Create two agents adjacent to each other, each with an AOE
  Agent agent1(5, 5, *agent_config, &test_resource_names);
  Agent agent2(5, 6, *agent_config, &test_resource_names);

  agent1.inventory.update(0, 100);
  agent2.inventory.update(0, 100);

  // Both agents have mobile AOE
  AOEConfig config = create_aoe_config(1, 0, 5, false, false);  // +5 health, effect_self=false
  tracker->register_source(agent1, config);
  tracker->register_source(agent2, config);

  // Apply mobile AOE
  std::vector<Agent*> agents = {&agent1, &agent2};
  tracker->apply_mobile(agents);

  // Both agents should affect each other
  EXPECT_EQ(105, agent1.inventory.amount(0));  // Agent2's AOE affects Agent1
  EXPECT_EQ(105, agent2.inventory.amount(0));  // Agent1's AOE affects Agent2
}

// ==================== Presence Delta Tests ====================

TEST_F(AOETrackerTest, FixedAOEPresenceDeltaEnter) {
  TestObject source("buffer", 5, 5);
  TestObject target("agent", 5, 6);  // In range

  target.inventory.update(0, 100);

  // AOE with presence delta (+50 on enter)
  AOEConfig config = create_aoe_config_with_presence(1, 0, 50, true);

  tracker->register_source(source, config);

  // First apply - target enters AOE
  tracker->apply_fixed(target);

  // Target should have presence delta applied
  EXPECT_EQ(150, target.inventory.amount(0));

  // Second apply - target stays in AOE (no change)
  tracker->apply_fixed(target);
  EXPECT_EQ(150, target.inventory.amount(0));
}

TEST_F(AOETrackerTest, FixedAOEPresenceDeltaExit) {
  TestObject source("buffer", 5, 5);
  TestObject target("agent", 5, 6);  // In range

  target.inventory.update(0, 100);

  // AOE with presence delta (+50 on enter, -50 on exit)
  AOEConfig config = create_aoe_config_with_presence(1, 0, 50, true);

  tracker->register_source(source, config);

  // Enter AOE
  tracker->apply_fixed(target);
  EXPECT_EQ(150, target.inventory.amount(0));

  // Move target out of range
  target.location.r = 0;
  target.location.c = 0;

  // Apply - target exits AOE
  tracker->apply_fixed(target);

  // Exit delta should be applied (-50)
  EXPECT_EQ(100, target.inventory.amount(0));
}

// ==================== Boundary Tests ====================

TEST_F(AOETrackerTest, FixedAOEBoundaryEffects) {
  // Source at corner (0, 0)
  TestObject source("healer", 0, 0);

  AOEConfig config = create_aoe_config(2, 0, 10, true, false);

  tracker->register_source(source, config);

  // Should be registered at valid cells only
  EXPECT_EQ(1u, tracker->fixed_effect_count_at(GridLocation(0, 0)));
  EXPECT_EQ(1u, tracker->fixed_effect_count_at(GridLocation(0, 1)));
  EXPECT_EQ(1u, tracker->fixed_effect_count_at(GridLocation(1, 0)));
  EXPECT_EQ(1u, tracker->fixed_effect_count_at(GridLocation(0, 2)));
  EXPECT_EQ(1u, tracker->fixed_effect_count_at(GridLocation(2, 0)));
  EXPECT_EQ(1u, tracker->fixed_effect_count_at(GridLocation(1, 1)));
}

// ==================== Range Calculation Tests ====================

TEST_F(AOETrackerTest, ChebyshevDistance) {
  // Verify L-infinity (Chebyshev) distance is used
  TestObject source("healer", 5, 5);

  AOEConfig config = create_aoe_config(2, 0, 10, true, false);

  tracker->register_source(source, config);

  // Cells at Chebyshev distance 2 should be affected (including diagonals)
  EXPECT_EQ(1u, tracker->fixed_effect_count_at(GridLocation(3, 3)));  // diagonal distance 2
  EXPECT_EQ(1u, tracker->fixed_effect_count_at(GridLocation(3, 7)));
  EXPECT_EQ(1u, tracker->fixed_effect_count_at(GridLocation(7, 3)));
  EXPECT_EQ(1u, tracker->fixed_effect_count_at(GridLocation(7, 7)));

  // Cells at Chebyshev distance 3 should NOT be affected
  EXPECT_EQ(0u, tracker->fixed_effect_count_at(GridLocation(2, 5)));
  EXPECT_EQ(0u, tracker->fixed_effect_count_at(GridLocation(8, 5)));
}
