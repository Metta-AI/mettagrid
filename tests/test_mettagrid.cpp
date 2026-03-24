#include <gtest/gtest.h>

#include <array>
#include <cmath>
#include <random>
#include <utility>

#include "actions/attack.hpp"
#include "actions/change_vibe.hpp"
#include "actions/noop.hpp"
#include "config/mettagrid_config.hpp"
#include "config/observation_features.hpp"
#include "core/game_value.hpp"
#include "core/game_value_config.hpp"
#include "core/grid.hpp"
#include "core/query_config.hpp"
#include "core/types.hpp"
#include "handler/handler_context.hpp"
#include "objects/agent.hpp"
#include "objects/agent_config.hpp"
#include "objects/constants.hpp"
#include "objects/inventory.hpp"
#include "objects/inventory_config.hpp"
#include "objects/protocol.hpp"
#include "objects/reward_config.hpp"
#include "objects/wall.hpp"
#include "systems/stats_tracker.hpp"

// Test-specific inventory item type constants
namespace TestItems {
constexpr uint8_t ORE = 0;
constexpr uint8_t LASER = 1;
constexpr uint8_t ARMOR = 2;
constexpr uint8_t HEART = 3;
}  // namespace TestItems

namespace TestItemStrings {
const char ORE[] = "ore_red";
const char LASER[] = "laser";
const char ARMOR[] = "armor";
const char HEART[] = "heart";
}  // namespace TestItemStrings

namespace TestRewards {
constexpr float ORE = 0.125f;
constexpr float LASER = 0.0f;
constexpr float ARMOR = 0.0f;
constexpr float HEART = 1.0f;
}  // namespace TestRewards

// Pure C++ tests without any Python/pybind dependencies - we will test those with pytest
class MettaGridCppTest : public ::testing::Test {
protected:
  void SetUp() override {
    // Initialize ObservationFeature constants for tests
    // Use standard feature IDs that match what the game would use
    std::unordered_map<std::string, ObservationType> feature_ids = {
        {"type_id", 0},
        {"agent:group", 1},
        {"agent:frozen", 2},
        {"episode_completion_pct", 7},
        {"last_action", 8},
        {"goal", 9},
        {"last_reward", 10},
        {"vibe", 11},
        {"agent:vibe", 12},
        {"tag", 15},
    };
    ObservationFeature::Initialize(feature_ids);
    resource_names = create_test_resource_names();
    stats_tracker = std::make_unique<StatsTracker>(&resource_names);
  }

  void TearDown() override {}

  // Helper function to create test resource_limits map
  InventoryConfig create_test_inventory_config() {
    InventoryConfig inventory_config;
    inventory_config.limit_defs = {
        LimitDef({TestItems::ORE}, 50),
        LimitDef({TestItems::LASER}, 50),
        LimitDef({TestItems::ARMOR}, 50),
        LimitDef({TestItems::HEART}, 50),
    };
    return inventory_config;
  }

  std::vector<std::string> create_test_resource_names() {
    return {TestItemStrings::ORE, TestItemStrings::LASER, TestItemStrings::ARMOR, TestItemStrings::HEART};
  }

  // Helper: create a RewardEntry for an agent STAT with optional max
  static RewardEntry make_stat_entry(const std::string& stat_name,
                                     float weight,
                                     float max_val = 0.0f,
                                     GameValueScope scope = GameValueScope::AGENT) {
    RewardEntry entry;
    StatValueConfig stat_cfg;
    stat_cfg.scope = scope;
    stat_cfg.stat_name = stat_name;
    auto sum_cfg = std::make_shared<SumValueConfig>();
    sum_cfg->values = {stat_cfg};
    sum_cfg->weights = {weight};
    if (max_val > 0.0f) {
      auto min_cfg = std::make_shared<MinValueConfig>();
      ConstValueConfig max_cfg;
      max_cfg.value = max_val;
      min_cfg->values = {GameValueConfig(sum_cfg), GameValueConfig(max_cfg)};
      entry.reward = min_cfg;
    } else {
      entry.reward = sum_cfg;
    }
    return entry;
  }

  RewardConfig create_test_reward_config() {
    RewardConfig cfg;
    cfg.entries.push_back(make_stat_entry(std::string(TestItemStrings::ORE) + ".amount", TestRewards::ORE, 10.0f));
    cfg.entries.push_back(make_stat_entry(std::string(TestItemStrings::LASER) + ".amount", TestRewards::LASER, 10.0f));
    cfg.entries.push_back(make_stat_entry(std::string(TestItemStrings::ARMOR) + ".amount", TestRewards::ARMOR, 10.0f));
    cfg.entries.push_back(make_stat_entry(std::string(TestItemStrings::HEART) + ".amount", TestRewards::HEART));
    return cfg;
  }

  AgentConfig create_test_agent_config() {
    return AgentConfig(0,                               // type_id
                       "agent",                         // type_name
                       1,                               // group_id
                       "test_group",                    // group_name
                       0,                               // initial_vibe
                       create_test_inventory_config(),  // inventory_config
                       create_test_reward_config());    // reward_config
  }

  std::vector<std::string> resource_names;
  std::unique_ptr<StatsTracker> stats_tracker;
};

// ==================== Agent Tests ====================

TEST_F(MettaGridCppTest, ResolveGameValueConst) {
  ConstValueConfig cfg;
  cfg.value = 4.5f;

  mettagrid::HandlerContext ctx;
  auto resolved = resolve_game_value(cfg, ctx);
  EXPECT_FLOAT_EQ(resolved.read(), 4.5f);
}

TEST_F(MettaGridCppTest, ResolveGameValueInventory) {
  AgentConfig agent_cfg = create_test_agent_config();
  auto resources = create_test_resource_names();
  std::unique_ptr<Agent> agent(new Agent(0, 0, agent_cfg, &resources));
  agent->inventory.update(TestItems::ORE, 7);

  InventoryValueConfig cfg;
  cfg.id = TestItems::ORE;
  cfg.scope = GameValueScope::AGENT;

  mettagrid::HandlerContext ctx;
  ctx.actor = agent.get();
  auto resolved = resolve_game_value(cfg, ctx);
  EXPECT_FLOAT_EQ(resolved.read(), 7.0f);
}

TEST_F(MettaGridCppTest, ResolveGameValueStatAgentAndGame) {
  AgentConfig agent_cfg = create_test_agent_config();
  auto resources = create_test_resource_names();
  std::unique_ptr<Agent> agent(new Agent(0, 0, agent_cfg, &resources));
  agent->stats.add("agent.score", 12.0f);
  stats_tracker->add("game.score", 21.0f);

  StatValueConfig agent_stat_cfg;
  agent_stat_cfg.scope = GameValueScope::AGENT;
  agent_stat_cfg.stat_name = "agent.score";

  StatValueConfig game_stat_cfg;
  game_stat_cfg.scope = GameValueScope::GAME;
  game_stat_cfg.stat_name = "game.score";

  mettagrid::HandlerContext ctx;
  ctx.actor = agent.get();
  ctx.game_stats = stats_tracker.get();

  auto agent_resolved = resolve_game_value(agent_stat_cfg, ctx);
  auto game_resolved = resolve_game_value(game_stat_cfg, ctx);
  EXPECT_FLOAT_EQ(agent_resolved.read(), 12.0f);
  EXPECT_FLOAT_EQ(game_resolved.read(), 21.0f);
}

TEST_F(MettaGridCppTest, ResolveGameValueQueryCount) {
  mettagrid::TagIndex tag_index;
  WallConfig wall_cfg(1, "wall");
  wall_cfg.tag_ids = {42};
  Wall wall1(0, 0, wall_cfg);
  Wall wall2(1, 0, wall_cfg);
  tag_index.register_object(&wall1);
  tag_index.register_object(&wall2);

  auto tag_query = std::make_shared<mettagrid::TagQueryConfig>();
  tag_query->tag_id = 42;

  QueryCountValueConfig cfg;
  cfg.query = tag_query;

  mettagrid::HandlerContext ctx;
  ctx.tag_index = &tag_index;
  auto resolved = resolve_game_value(cfg, ctx);
  EXPECT_FLOAT_EQ(resolved.read(), 2.0f);
}

TEST_F(MettaGridCppTest, ResolveGameValueQueryInventory) {
  mettagrid::TagIndex tag_index;
  AgentConfig agent_cfg = create_test_agent_config();
  agent_cfg.tag_ids = {77};
  auto resources = create_test_resource_names();
  Agent agent1(0, 0, agent_cfg, &resources);
  Agent agent2(1, 0, agent_cfg, &resources);
  agent1.inventory.update(TestItems::ORE, 3);
  agent2.inventory.update(TestItems::ORE, 4);
  tag_index.register_object(&agent1);
  tag_index.register_object(&agent2);

  auto tag_query = std::make_shared<mettagrid::TagQueryConfig>();
  tag_query->tag_id = 77;

  QueryInventoryValueConfig cfg;
  cfg.id = TestItems::ORE;
  cfg.query = tag_query;

  mettagrid::HandlerContext ctx;
  ctx.tag_index = &tag_index;
  auto resolved = resolve_game_value(cfg, ctx);
  EXPECT_FLOAT_EQ(resolved.read(), 7.0f);
}

TEST_F(MettaGridCppTest, ResolveGameValueSumLinearAndLog) {
  auto linear_cfg = std::make_shared<SumValueConfig>();
  ConstValueConfig c1;
  c1.value = 2.0f;
  ConstValueConfig c2;
  c2.value = 3.0f;
  linear_cfg->values = {c1, c2};

  mettagrid::HandlerContext ctx;
  auto linear_resolved = resolve_game_value(GameValueConfig(linear_cfg), ctx);
  EXPECT_FLOAT_EQ(linear_resolved.read(), 5.0f);

  auto log_cfg = std::make_shared<SumValueConfig>();
  ConstValueConfig c3;
  c3.value = 3.0f;
  ConstValueConfig c4;
  c4.value = 8.0f;
  log_cfg->values = {c3, c4};
  log_cfg->weights = {2.0f, 0.5f};
  log_cfg->log = true;

  auto log_resolved = resolve_game_value(GameValueConfig(log_cfg), ctx);
  float expected = 2.0f * std::log(3.0f + 1.0f) + 0.5f * std::log(8.0f + 1.0f);
  EXPECT_NEAR(log_resolved.read(), expected, 1e-6f);
}

TEST_F(MettaGridCppTest, ResolveGameValueMaxAndMin) {
  auto max_cfg = std::make_shared<MaxValueConfig>();
  ConstValueConfig c1;
  c1.value = 2.0f;
  ConstValueConfig c2;
  c2.value = 7.0f;
  ConstValueConfig c3;
  c3.value = 4.0f;
  max_cfg->values = {c1, c2, c3};

  auto min_cfg = std::make_shared<MinValueConfig>();
  min_cfg->values = {c1, c2, c3};

  mettagrid::HandlerContext ctx;
  auto max_resolved = resolve_game_value(GameValueConfig(max_cfg), ctx);
  auto min_resolved = resolve_game_value(GameValueConfig(min_cfg), ctx);
  EXPECT_FLOAT_EQ(max_resolved.read(), 7.0f);
  EXPECT_FLOAT_EQ(min_resolved.read(), 2.0f);
}

TEST_F(MettaGridCppTest, AgentRewards) {
  AgentConfig agent_cfg = create_test_agent_config();
  auto resource_names = create_test_resource_names();
  std::unique_ptr<Agent> agent(new Agent(0, 0, agent_cfg, &resource_names));

  // Test reward config entries
  const auto& entries = agent->reward_helper.config.entries;
  EXPECT_EQ(entries.size(), 4);
  EXPECT_TRUE(std::holds_alternative<std::shared_ptr<MinValueConfig>>(entries[0].reward));
  EXPECT_TRUE(std::holds_alternative<std::shared_ptr<MinValueConfig>>(entries[1].reward));
  EXPECT_TRUE(std::holds_alternative<std::shared_ptr<MinValueConfig>>(entries[2].reward));
  EXPECT_TRUE(std::holds_alternative<std::shared_ptr<SumValueConfig>>(entries[3].reward));
}

TEST_F(MettaGridCppTest, AgentInventoryUpdate) {
  AgentConfig agent_cfg = create_test_agent_config();
  auto resource_names = create_test_resource_names();
  std::unique_ptr<Agent> agent(new Agent(0, 0, agent_cfg, &resource_names));

  float agent_reward = 0.0f;
  agent->init(&agent_reward);
  mettagrid::HandlerContext reward_ctx;
  reward_ctx.actor = agent.get();
  agent->reward_helper.init_entries(reward_ctx);

  // Test adding items
  int delta = agent->inventory.update(TestItems::ORE, 5);
  EXPECT_EQ(delta, 5);
  EXPECT_EQ(agent->inventory.amount(TestItems::ORE), 5);
  agent->reward_helper.compute_entries();
  EXPECT_FLOAT_EQ(agent_reward, 0.625f);  // 5 * 0.125

  // Test removing items
  delta = agent->inventory.update(TestItems::ORE, -2);
  EXPECT_EQ(delta, -2);
  EXPECT_EQ(agent->inventory.amount(TestItems::ORE), 3);
  agent->reward_helper.compute_entries();
  EXPECT_FLOAT_EQ(agent_reward, 0.375f);  // 3 * 0.125

  // Test hitting zero
  delta = agent->inventory.update(TestItems::ORE, -10);
  EXPECT_EQ(delta, -3);  // Should only remove what's available
  // check that the item is not in the inventory
  EXPECT_EQ(agent->inventory.amount(TestItems::ORE), 0);
  agent->reward_helper.compute_entries();
  EXPECT_FLOAT_EQ(agent_reward, 0.0f);

  // Test hitting resource_limits limit
  agent->inventory.update(TestItems::ORE, 30);
  delta = agent->inventory.update(TestItems::ORE, 50);  // resource_limits is 50
  EXPECT_EQ(delta, 20);                                 // Should only add up to resource_limits
  EXPECT_EQ(agent->inventory.amount(TestItems::ORE), 50);
  agent->reward_helper.compute_entries();
  EXPECT_FLOAT_EQ(agent_reward, 6.25f);  // 50 * 0.125
}

TEST_F(MettaGridCppTest, AgentInventoryStatsUpdate) {
  AgentConfig agent_cfg = create_test_agent_config();
  auto resource_names = create_test_resource_names();
  std::unique_ptr<Agent> agent(new Agent(0, 0, agent_cfg, &resource_names));

  float agent_reward = 0.0f;
  agent->init(&agent_reward);

  // Test that stats are updated when inventory changes via inventory.update() directly
  // This verifies the on_inventory_change callback mechanism

  // Initial state: no stats should be set
  EXPECT_FLOAT_EQ(agent->stats.get(std::string(TestItemStrings::ORE) + ".amount"), 0.0f);
  EXPECT_FLOAT_EQ(agent->stats.get(std::string(TestItemStrings::ORE) + ".gained"), 0.0f);
  EXPECT_FLOAT_EQ(agent->stats.get(std::string(TestItemStrings::ORE) + ".lost"), 0.0f);

  InventoryDelta delta1 = agent->inventory.update(TestItems::ORE, 10);
  EXPECT_EQ(delta1, 10);
  EXPECT_EQ(agent->inventory.amount(TestItems::ORE), 10);

  // Verify stats were updated via callback
  EXPECT_FLOAT_EQ(agent->stats.get(std::string(TestItemStrings::ORE) + ".amount"), 10.0f);
  EXPECT_FLOAT_EQ(agent->stats.get(std::string(TestItemStrings::ORE) + ".gained"), 10.0f);
  EXPECT_FLOAT_EQ(agent->stats.get(std::string(TestItemStrings::ORE) + ".lost"), 0.0f);

  // Add more items
  InventoryDelta delta2 = agent->inventory.update(TestItems::ORE, 5);
  EXPECT_EQ(delta2, 5);
  EXPECT_EQ(agent->inventory.amount(TestItems::ORE), 15);

  // Verify stats accumulated correctly
  EXPECT_FLOAT_EQ(agent->stats.get(std::string(TestItemStrings::ORE) + ".amount"), 15.0f);
  EXPECT_FLOAT_EQ(agent->stats.get(std::string(TestItemStrings::ORE) + ".gained"), 15.0f);  // 10 + 5
  EXPECT_FLOAT_EQ(agent->stats.get(std::string(TestItemStrings::ORE) + ".lost"), 0.0f);

  // Remove items
  InventoryDelta delta3 = agent->inventory.update(TestItems::ORE, -7);
  EXPECT_EQ(delta3, -7);
  EXPECT_EQ(agent->inventory.amount(TestItems::ORE), 8);

  // Verify stats updated correctly
  EXPECT_FLOAT_EQ(agent->stats.get(std::string(TestItemStrings::ORE) + ".amount"), 8.0f);
  EXPECT_FLOAT_EQ(agent->stats.get(std::string(TestItemStrings::ORE) + ".gained"), 15.0f);  // Unchanged
  EXPECT_FLOAT_EQ(agent->stats.get(std::string(TestItemStrings::ORE) + ".lost"), 7.0f);     // 0 + 7

  // Remove more items
  InventoryDelta delta4 = agent->inventory.update(TestItems::ORE, -3);
  EXPECT_EQ(delta4, -3);
  EXPECT_EQ(agent->inventory.amount(TestItems::ORE), 5);

  // Verify stats updated correctly
  EXPECT_FLOAT_EQ(agent->stats.get(std::string(TestItemStrings::ORE) + ".amount"), 5.0f);
  EXPECT_FLOAT_EQ(agent->stats.get(std::string(TestItemStrings::ORE) + ".gained"), 15.0f);  // Unchanged
  EXPECT_FLOAT_EQ(agent->stats.get(std::string(TestItemStrings::ORE) + ".lost"), 10.0f);    // 7 + 3

  // Test with a different resource (LASER)
  InventoryDelta delta5 = agent->inventory.update(TestItems::LASER, 20);
  EXPECT_EQ(delta5, 20);
  EXPECT_EQ(agent->inventory.amount(TestItems::LASER), 20);

  // Verify LASER stats were updated
  EXPECT_FLOAT_EQ(agent->stats.get(std::string(TestItemStrings::LASER) + ".amount"), 20.0f);
  EXPECT_FLOAT_EQ(agent->stats.get(std::string(TestItemStrings::LASER) + ".gained"), 20.0f);
  EXPECT_FLOAT_EQ(agent->stats.get(std::string(TestItemStrings::LASER) + ".lost"), 0.0f);

  // Test that zero delta doesn't update stats (but callback should still be called)
  InventoryDelta delta6 = agent->inventory.update(TestItems::ORE, 0);
  EXPECT_EQ(delta6, 0);
  EXPECT_EQ(agent->inventory.amount(TestItems::ORE), 5);

  // Stats should remain unchanged (delta was 0, so no stats update in callback)
  EXPECT_FLOAT_EQ(agent->stats.get(std::string(TestItemStrings::ORE) + ".amount"), 5.0f);
  EXPECT_FLOAT_EQ(agent->stats.get(std::string(TestItemStrings::ORE) + ".gained"), 15.0f);
  EXPECT_FLOAT_EQ(agent->stats.get(std::string(TestItemStrings::ORE) + ".lost"), 10.0f);

  // Test hitting limit - stats should reflect actual change, not attempted change
  agent->inventory.update(TestItems::ORE, 50);                           // Fill to limit
  InventoryDelta delta7 = agent->inventory.update(TestItems::ORE, 100);  // Try to add 100, but limit is 50
  EXPECT_EQ(delta7, 0);                                                  // No change because already at limit
  EXPECT_EQ(agent->inventory.amount(TestItems::ORE), 50);

  // Stats should reflect only the actual change (0), so no update
  EXPECT_FLOAT_EQ(agent->stats.get(std::string(TestItemStrings::ORE) + ".amount"), 50.0f);
  EXPECT_FLOAT_EQ(agent->stats.get(std::string(TestItemStrings::ORE) + ".gained"),
                  60.0f);  // 15 + 45 (from filling to limit)
  EXPECT_FLOAT_EQ(agent->stats.get(std::string(TestItemStrings::ORE) + ".lost"), 10.0f);
}
// Test for reward capping behavior with a lower cap to actually hit it
TEST_F(MettaGridCppTest, AgentInventoryUpdate_RewardCappingBehavior) {
  // Create a custom config with a lower ore reward cap that we can actually hit
  auto inventory_config = create_test_inventory_config();

  RewardConfig reward_cfg;
  // ORE with low cap of 2.0
  reward_cfg.entries.push_back(make_stat_entry(std::string(TestItemStrings::ORE) + ".amount", TestRewards::ORE, 2.0f));
  reward_cfg.entries.push_back(
      make_stat_entry(std::string(TestItemStrings::LASER) + ".amount", TestRewards::LASER, 10.0f));
  reward_cfg.entries.push_back(
      make_stat_entry(std::string(TestItemStrings::ARMOR) + ".amount", TestRewards::ARMOR, 10.0f));
  reward_cfg.entries.push_back(make_stat_entry(std::string(TestItemStrings::HEART) + ".amount", TestRewards::HEART));

  AgentConfig agent_cfg(0, "agent", 1, "test_group", 0, inventory_config, reward_cfg);

  auto resource_names = create_test_resource_names();
  std::unique_ptr<Agent> agent(new Agent(0, 0, agent_cfg, &resource_names));
  float agent_reward = 0.0f;
  agent->init(&agent_reward);
  mettagrid::HandlerContext reward_ctx;
  reward_ctx.actor = agent.get();
  agent->reward_helper.init_entries(reward_ctx);

  // Test 1: Add items up to the cap
  // 16 ORE * 0.125 = 2.0 (exactly at cap)
  int delta = agent->inventory.update(TestItems::ORE, 16);
  EXPECT_EQ(delta, 16);
  EXPECT_EQ(agent->inventory.amount(TestItems::ORE), 16);
  agent->reward_helper.compute_entries();
  EXPECT_FLOAT_EQ(agent_reward, 2.0f);

  // Test 2: Add more items beyond the cap
  // 32 ORE * 0.125 = 4.0, but capped at 2.0
  delta = agent->inventory.update(TestItems::ORE, 16);
  EXPECT_EQ(delta, 16);
  EXPECT_EQ(agent->inventory.amount(TestItems::ORE), 32);
  agent->reward_helper.compute_entries();
  EXPECT_FLOAT_EQ(agent_reward, 2.0f);  // Still capped at 2.0

  // Test 3: Remove some items while still over cap
  // 24 ORE * 0.125 = 3.0, but still capped at 2.0
  delta = agent->inventory.update(TestItems::ORE, -8);
  EXPECT_EQ(delta, -8);
  EXPECT_EQ(agent->inventory.amount(TestItems::ORE), 24);
  agent->reward_helper.compute_entries();
  EXPECT_FLOAT_EQ(agent_reward, 2.0f);  // Should remain at cap

  // Test 4: Remove enough items to go below cap
  // 12 ORE * 0.125 = 1.5 (now below cap)
  delta = agent->inventory.update(TestItems::ORE, -12);
  EXPECT_EQ(delta, -12);
  EXPECT_EQ(agent->inventory.amount(TestItems::ORE), 12);
  agent->reward_helper.compute_entries();
  EXPECT_FLOAT_EQ(agent_reward, 1.5f);  // Now tracking actual value

  // Test 5: Add items again, but not enough to hit cap
  // 14 ORE * 0.125 = 1.75 (still below cap)
  delta = agent->inventory.update(TestItems::ORE, 2);
  EXPECT_EQ(delta, 2);
  EXPECT_EQ(agent->inventory.amount(TestItems::ORE), 14);
  agent->reward_helper.compute_entries();
  EXPECT_FLOAT_EQ(agent_reward, 1.75f);

  // Test 6: Add items to go over cap again
  // 20 ORE * 0.125 = 2.5, but capped at 2.0
  delta = agent->inventory.update(TestItems::ORE, 6);
  EXPECT_EQ(delta, 6);
  EXPECT_EQ(agent->inventory.amount(TestItems::ORE), 20);
  agent->reward_helper.compute_entries();
  EXPECT_FLOAT_EQ(agent_reward, 2.0f);
}

// Test multiple item types with different caps
TEST_F(MettaGridCppTest, AgentInventoryUpdate_MultipleItemCaps) {
  auto inventory_config = create_test_inventory_config();

  RewardConfig reward_cfg;
  reward_cfg.entries.push_back(make_stat_entry(std::string(TestItemStrings::ORE) + ".amount", TestRewards::ORE, 2.0f));
  reward_cfg.entries.push_back(make_stat_entry(std::string(TestItemStrings::LASER) + ".amount", TestRewards::LASER));
  reward_cfg.entries.push_back(make_stat_entry(std::string(TestItemStrings::ARMOR) + ".amount", TestRewards::ARMOR));
  reward_cfg.entries.push_back(
      make_stat_entry(std::string(TestItemStrings::HEART) + ".amount", TestRewards::HEART, 30.0f));

  AgentConfig agent_cfg(0, "agent", 1, "test_group", 0, inventory_config, reward_cfg);

  auto resource_names = create_test_resource_names();
  std::unique_ptr<Agent> agent(new Agent(0, 0, agent_cfg, &resource_names));
  float agent_reward = 0.0f;
  agent->init(&agent_reward);
  mettagrid::HandlerContext reward_ctx;
  reward_ctx.actor = agent.get();
  agent->reward_helper.init_entries(reward_ctx);

  // Add ORE beyond its cap
  agent->inventory.update(TestItems::ORE, 50);  // 50 * 0.125 = 6.25, capped at 2.0
  EXPECT_EQ(agent->inventory.amount(TestItems::ORE), 50);
  agent->reward_helper.compute_entries();
  EXPECT_FLOAT_EQ(agent_reward, 2.0f);

  // Add HEART up to its cap
  agent->inventory.update(TestItems::HEART, 30);  // 30 * 1.0 = 30.0
  EXPECT_EQ(agent->inventory.amount(TestItems::HEART), 30);
  agent->reward_helper.compute_entries();
  EXPECT_FLOAT_EQ(agent_reward, 32.0f);  // 2.0 + 30.0

  // Add more HEART beyond its cap
  agent->inventory.update(TestItems::HEART, 10);  // 40 * 1.0 = 40.0, capped at 30.0
  EXPECT_EQ(agent->inventory.amount(TestItems::HEART), 40);
  agent->reward_helper.compute_entries();
  EXPECT_FLOAT_EQ(agent_reward, 32.0f);  // Still 2.0 + 30.0

  // Remove some ORE (still over cap)
  agent->inventory.update(TestItems::ORE, -10);  // 40 * 0.125 = 5.0, still capped at 2.0
  EXPECT_EQ(agent->inventory.amount(TestItems::ORE), 40);
  agent->reward_helper.compute_entries();
  EXPECT_FLOAT_EQ(agent_reward, 32.0f);  // No change

  // Remove ORE to go below cap
  agent->inventory.update(TestItems::ORE, -35);  // 5 * 0.125 = 0.625
  EXPECT_EQ(agent->inventory.amount(TestItems::ORE), 5);
  agent->reward_helper.compute_entries();
  EXPECT_FLOAT_EQ(agent_reward, 30.625f);  // 0.625 + 30.0

  // Remove HEART to go below its cap
  agent->inventory.update(TestItems::HEART, -15);  // 25 * 1.0 = 25.0
  EXPECT_EQ(agent->inventory.amount(TestItems::HEART), 25);
  agent->reward_helper.compute_entries();
  EXPECT_FLOAT_EQ(agent_reward, 25.625f);  // 0.625 + 25.0
}

// Test shared inventory limits between multiple resources
TEST_F(MettaGridCppTest, SharedInventoryLimits) {
  // Create an inventory config where ORE and LASER share a combined limit
  InventoryConfig inventory_config;
  inventory_config.limit_defs = {
      LimitDef({TestItems::ORE, TestItems::LASER}, 30),  // ORE and LASER share a limit of 30 total
      LimitDef({TestItems::ARMOR}, 50),                  // ARMOR has its own separate limit
      {{TestItems::HEART}, 50},                          // HEART has its own separate limit
  };

  RewardConfig reward_cfg = create_test_reward_config();
  AgentConfig agent_cfg(0, "agent", 1, "test_group", 0, inventory_config, reward_cfg);

  auto resource_names = create_test_resource_names();
  std::unique_ptr<Agent> agent(new Agent(0, 0, agent_cfg, &resource_names));
  float agent_reward = 0.0f;
  agent->init(&agent_reward);

  // Add ORE up to 20
  int delta = agent->inventory.update(TestItems::ORE, 20);
  EXPECT_EQ(delta, 20);
  EXPECT_EQ(agent->inventory.amount(TestItems::ORE), 20);

  // Try to add 20 LASER - should only add 10 due to shared limit
  delta = agent->inventory.update(TestItems::LASER, 20);
  EXPECT_EQ(delta, 10);  // Only 10 can be added (20 ORE + 10 LASER = 30 total)
  EXPECT_EQ(agent->inventory.amount(TestItems::LASER), 10);

  // Try to add more ORE - should fail as we're at the shared limit
  delta = agent->inventory.update(TestItems::ORE, 5);
  EXPECT_EQ(delta, 0);  // Can't add any more
  EXPECT_EQ(agent->inventory.amount(TestItems::ORE), 20);

  // Remove some LASER
  delta = agent->inventory.update(TestItems::LASER, -5);
  EXPECT_EQ(delta, -5);
  EXPECT_EQ(agent->inventory.amount(TestItems::LASER), 5);

  // Now we can add more ORE since we freed up shared space
  delta = agent->inventory.update(TestItems::ORE, 5);
  EXPECT_EQ(delta, 5);
  EXPECT_EQ(agent->inventory.amount(TestItems::ORE), 25);

  // ARMOR should work independently with its own limit
  delta = agent->inventory.update(TestItems::ARMOR, 40);
  EXPECT_EQ(delta, 40);
  EXPECT_EQ(agent->inventory.amount(TestItems::ARMOR), 40);

  // Can still add more ARMOR up to its limit
  delta = agent->inventory.update(TestItems::ARMOR, 20);
  EXPECT_EQ(delta, 10);  // Should cap at 50
  EXPECT_EQ(agent->inventory.amount(TestItems::ARMOR), 50);

  // Remove all ORE
  delta = agent->inventory.update(TestItems::ORE, -25);
  EXPECT_EQ(delta, -25);
  EXPECT_EQ(agent->inventory.amount(TestItems::ORE), 0);

  // Now we can add up to 25 more LASER (5 existing + 25 = 30)
  delta = agent->inventory.update(TestItems::LASER, 30);
  EXPECT_EQ(delta, 25);
  EXPECT_EQ(agent->inventory.amount(TestItems::LASER), 30);

  // Verify final state
  EXPECT_EQ(agent->inventory.amount(TestItems::ORE), 0);
  EXPECT_EQ(agent->inventory.amount(TestItems::LASER), 30);
  EXPECT_EQ(agent->inventory.amount(TestItems::ARMOR), 50);
  EXPECT_EQ(agent->inventory.amount(TestItems::HEART), 0);
}

// ==================== Grid Tests ====================

TEST_F(MettaGridCppTest, GridCreation) {
  Grid grid(5, 10);  // row/height, col/width

  EXPECT_EQ(grid.width, 10);
  EXPECT_EQ(grid.height, 5);
}

TEST_F(MettaGridCppTest, GridObjectManagement) {
  Grid grid(10, 10);

  // Create and add an agent
  AgentConfig agent_cfg = create_test_agent_config();
  auto resource_names = create_test_resource_names();
  Agent* agent = new Agent(2, 3, agent_cfg, &resource_names);

  grid.add_object(agent);

  EXPECT_NE(agent->id, 0);  // Should have been assigned a valid ID
  EXPECT_EQ(agent->location.r, 2);
  EXPECT_EQ(agent->location.c, 3);

  // Verify we can retrieve the agent
  auto retrieved_agent = grid.object(agent->id);
  EXPECT_EQ(retrieved_agent, agent);

  // Verify it's at the expected location
  auto agent_at_location = grid.object_at(GridLocation(2, 3));
  EXPECT_EQ(agent_at_location, agent);
}

// ==================== Action Tracking ====================

TEST_F(MettaGridCppTest, ActionTracking) {
  Grid grid(10, 10);

  AgentConfig agent_cfg = create_test_agent_config();
  auto resource_names = create_test_resource_names();
  Agent* agent = new Agent(5, 5, agent_cfg, &resource_names);
  float agent_reward = 0.0f;
  agent->init(&agent_reward);
  grid.add_object(agent);

  ActionConfig noop_cfg({}, {});
  Noop noop(noop_cfg);
  std::mt19937 rng(42);
  noop.init();

  mettagrid::HandlerContext ctx;
  ctx.grid = &grid;
  ctx.rng = &rng;

  EXPECT_FLOAT_EQ(agent->stats.get("status.max_steps_without_motion"), 0.0f);
  noop.handle_action(*agent, 0, ctx);  // count 1, max 1
  EXPECT_EQ(agent->location.r, 5);
  EXPECT_EQ(agent->location.c, 5);
  EXPECT_EQ(agent->prev_location.r, 5);
  EXPECT_EQ(agent->prev_location.c, 5);

  EXPECT_FLOAT_EQ(agent->stats.get("status.max_steps_without_motion"), 1.0f);
  agent->location.r = 6;
  agent->location.c = 6;
  noop.handle_action(*agent, 0, ctx);  // count 0, max 1
  EXPECT_EQ(agent->location.r, 6);
  EXPECT_EQ(agent->location.c, 6);
  EXPECT_EQ(agent->prev_location.r, 6);
  EXPECT_EQ(agent->prev_location.c, 6);
  EXPECT_FLOAT_EQ(agent->stats.get("status.max_steps_without_motion"), 1.0f);
  noop.handle_action(*agent, 0, ctx);  // count 1, max 1
  EXPECT_FLOAT_EQ(agent->stats.get("status.max_steps_without_motion"), 1.0f);
  noop.handle_action(*agent, 0, ctx);  // count 2, max 2
  noop.handle_action(*agent, 0, ctx);  // count 3, max 3
  EXPECT_FLOAT_EQ(agent->stats.get("status.max_steps_without_motion"), 3.0f);
  agent->location.r = 7;
  agent->location.c = 7;
  noop.handle_action(*agent, 0, ctx);  // count 0, max 3
  EXPECT_EQ(agent->location.r, 7);
  EXPECT_EQ(agent->location.c, 7);
  EXPECT_EQ(agent->prev_location.r, 7);
  EXPECT_EQ(agent->prev_location.c, 7);
  noop.handle_action(*agent, 0, ctx);  // count 1, max 3
  noop.handle_action(*agent, 0, ctx);  // count 2, max 3
  EXPECT_FLOAT_EQ(agent->stats.get("status.max_steps_without_motion"), 3.0f);
  noop.handle_action(*agent, 0, ctx);  // count 3, max 3
  noop.handle_action(*agent, 0, ctx);  // count 4, max 4
  EXPECT_FLOAT_EQ(agent->stats.get("status.max_steps_without_motion"), 4.0f);
}

// Tests for HasInventory::shared_update function
TEST_F(MettaGridCppTest, SharedUpdate_PositiveDelta_EvenDistribution) {
  // Test that positive delta is evenly distributed among agents
  InventoryConfig inv_cfg;
  inv_cfg.limit_defs = {LimitDef({TestItems::ORE}, 100)};

  AgentConfig agent_cfg(1, "test_agent", 1, "test_group");
  agent_cfg.inventory_config = inv_cfg;

  auto resource_names = create_test_resource_names();
  Agent agent1(0, 0, agent_cfg, &resource_names);
  Agent agent2(1, 0, agent_cfg, &resource_names);
  Agent agent3(2, 0, agent_cfg, &resource_names);

  std::vector<Inventory*> inventories = {&agent1.inventory, &agent2.inventory, &agent3.inventory};

  // Add 30 ore, should be distributed as 10 each
  InventoryDelta consumed = HasInventory::shared_update(inventories, TestItems::ORE, 30);

  EXPECT_EQ(consumed, 30);
  EXPECT_EQ(agent1.inventory.amount(TestItems::ORE), 10);
  EXPECT_EQ(agent2.inventory.amount(TestItems::ORE), 10);
  EXPECT_EQ(agent3.inventory.amount(TestItems::ORE), 10);
}

TEST_F(MettaGridCppTest, SharedUpdate_PositiveDelta_UnevenDistribution) {
  // Test that when delta doesn't divide evenly, earlier agents get more
  InventoryConfig inv_cfg;
  inv_cfg.limit_defs = {LimitDef({TestItems::ORE}, 100)};

  AgentConfig agent_cfg(1, "test_agent", 1, "test_group");
  agent_cfg.inventory_config = inv_cfg;

  auto resource_names = create_test_resource_names();
  Agent agent1(0, 0, agent_cfg, &resource_names);
  Agent agent2(1, 0, agent_cfg, &resource_names);
  Agent agent3(2, 0, agent_cfg, &resource_names);

  std::vector<Inventory*> inventories = {&agent1.inventory, &agent2.inventory, &agent3.inventory};

  // Add 31 ore, should be distributed as 11, 10, 10 (earlier agents get more)
  InventoryDelta consumed = HasInventory::shared_update(inventories, TestItems::ORE, 31);

  EXPECT_EQ(consumed, 31);
  EXPECT_EQ(agent1.inventory.amount(TestItems::ORE), 11);
  EXPECT_EQ(agent2.inventory.amount(TestItems::ORE), 10);
  EXPECT_EQ(agent3.inventory.amount(TestItems::ORE), 10);
}

TEST_F(MettaGridCppTest, SharedUpdate_PositiveDelta_WithLimits) {
  // Test that agents that hit their inventory limit drop out of distribution
  InventoryConfig inv_cfg;
  inv_cfg.limit_defs = {LimitDef({TestItems::ORE}, 10)};  // Low limit of 10

  AgentConfig agent_cfg(1, "test_agent", 1, "test_group");
  agent_cfg.inventory_config = inv_cfg;

  auto resource_names = create_test_resource_names();
  Agent agent1(0, 0, agent_cfg, &resource_names);
  Agent agent2(1, 0, agent_cfg, &resource_names);
  Agent agent3(2, 0, agent_cfg, &resource_names);

  // Pre-fill agent1 with 5 ore
  agent1.inventory.update(TestItems::ORE, 5);

  std::vector<Inventory*> inventories = {&agent1.inventory, &agent2.inventory, &agent3.inventory};

  // Try to add 30 ore
  // agent1 can only take 5 more (to reach limit of 10)
  // agent2 and agent3 can each take 10 (to reach their limits)
  // Total consumed will be 5 + 10 + 10 = 25, not the full 30
  InventoryDelta consumed = HasInventory::shared_update(inventories, TestItems::ORE, 30);

  EXPECT_EQ(consumed, 25);                                 // Only 25 can be consumed due to limits
  EXPECT_EQ(agent1.inventory.amount(TestItems::ORE), 10);  // Hit limit
  EXPECT_EQ(agent2.inventory.amount(TestItems::ORE), 10);  // Hit limit
  EXPECT_EQ(agent3.inventory.amount(TestItems::ORE), 10);  // Hit limit
}

TEST_F(MettaGridCppTest, SharedUpdate_NegativeDelta_EvenDistribution) {
  // Test that negative delta is evenly distributed among agents
  InventoryConfig inv_cfg;
  inv_cfg.limit_defs = {LimitDef({TestItems::ORE}, 100)};

  AgentConfig agent_cfg(1, "test_agent", 1, "test_group");
  agent_cfg.inventory_config = inv_cfg;

  auto resource_names = create_test_resource_names();
  Agent agent1(0, 0, agent_cfg, &resource_names);
  Agent agent2(1, 0, agent_cfg, &resource_names);
  Agent agent3(2, 0, agent_cfg, &resource_names);

  // Pre-fill agent inventories with 20 ore each
  agent1.inventory.update(TestItems::ORE, 20);
  agent2.inventory.update(TestItems::ORE, 20);
  agent3.inventory.update(TestItems::ORE, 20);

  std::vector<Inventory*> inventories = {&agent1.inventory, &agent2.inventory, &agent3.inventory};

  // Remove 30 ore, should remove 10 from each
  InventoryDelta consumed = HasInventory::shared_update(inventories, TestItems::ORE, -30);

  EXPECT_EQ(consumed, -30);
  EXPECT_EQ(agent1.inventory.amount(TestItems::ORE), 10);
  EXPECT_EQ(agent2.inventory.amount(TestItems::ORE), 10);
  EXPECT_EQ(agent3.inventory.amount(TestItems::ORE), 10);
}

TEST_F(MettaGridCppTest, SharedUpdate_NegativeDelta_InsufficientResources) {
  // Test behavior when some agents don't have enough to contribute their share
  InventoryConfig inv_cfg;
  inv_cfg.limit_defs = {LimitDef({TestItems::ORE}, 100)};

  AgentConfig agent_cfg(1, "test_agent", 1, "test_group");
  agent_cfg.inventory_config = inv_cfg;

  auto resource_names = create_test_resource_names();
  Agent agent1(0, 0, agent_cfg, &resource_names);
  Agent agent2(1, 0, agent_cfg, &resource_names);
  Agent agent3(2, 0, agent_cfg, &resource_names);

  // Pre-fill agent inventories with different amounts
  agent1.inventory.update(TestItems::ORE, 5);   // Only has 5
  agent2.inventory.update(TestItems::ORE, 20);  // Has plenty
  agent3.inventory.update(TestItems::ORE, 20);  // Has plenty

  std::vector<Inventory*> inventories = {&agent1.inventory, &agent2.inventory, &agent3.inventory};

  // Try to remove 30 ore
  // agent1 can only contribute 5, remaining 25 split between agent2 and agent3 as 13, 12
  InventoryDelta consumed = HasInventory::shared_update(inventories, TestItems::ORE, -30);

  EXPECT_EQ(consumed, -30);
  EXPECT_EQ(agent1.inventory.amount(TestItems::ORE), 0);  // Depleted
  EXPECT_EQ(agent2.inventory.amount(TestItems::ORE), 7);  // 20 - 13
  EXPECT_EQ(agent3.inventory.amount(TestItems::ORE), 8);  // 20 - 12
}

TEST_F(MettaGridCppTest, SharedUpdate_NegativeDelta_UnevenDistribution) {
  // Test that when negative delta doesn't divide evenly, earlier agents lose more
  InventoryConfig inv_cfg;
  inv_cfg.limit_defs = {LimitDef({TestItems::ORE}, 100)};

  AgentConfig agent_cfg(1, "test_agent", 1, "test_group");
  agent_cfg.inventory_config = inv_cfg;

  auto resource_names = create_test_resource_names();
  Agent agent1(0, 0, agent_cfg, &resource_names);
  Agent agent2(1, 0, agent_cfg, &resource_names);
  Agent agent3(2, 0, agent_cfg, &resource_names);

  // Pre-fill agent inventories with 20 ore each
  agent1.inventory.update(TestItems::ORE, 20);
  agent2.inventory.update(TestItems::ORE, 20);
  agent3.inventory.update(TestItems::ORE, 20);

  std::vector<Inventory*> inventories = {&agent1.inventory, &agent2.inventory, &agent3.inventory};

  // Remove 31 ore, should remove 11, 10, 10 (earlier agents lose more)
  InventoryDelta consumed = HasInventory::shared_update(inventories, TestItems::ORE, -31);

  EXPECT_EQ(consumed, -31);
  EXPECT_EQ(agent1.inventory.amount(TestItems::ORE), 9);   // 20 - 11
  EXPECT_EQ(agent2.inventory.amount(TestItems::ORE), 10);  // 20 - 10
  EXPECT_EQ(agent3.inventory.amount(TestItems::ORE), 10);  // 20 - 10
}

TEST_F(MettaGridCppTest, SharedUpdate_EmptyInventoriesList) {
  // Test with empty inventory havers list
  std::vector<Inventory*> inventories;

  InventoryDelta consumed = HasInventory::shared_update(inventories, TestItems::ORE, 10);

  EXPECT_EQ(consumed, 0);  // Nothing consumed since no inventory havers
}

TEST_F(MettaGridCppTest, SharedUpdate_SingleInventory) {
  // Test with single agent
  InventoryConfig inv_cfg;
  inv_cfg.limit_defs = {LimitDef({TestItems::ORE}, 100)};

  AgentConfig agent_cfg(1, "test_agent", 1, "test_group");
  agent_cfg.inventory_config = inv_cfg;

  auto resource_names = create_test_resource_names();
  Agent agent1(0, 0, agent_cfg, &resource_names);
  std::vector<Inventory*> inventories = {&agent1.inventory};

  // All delta should go to the single agent
  InventoryDelta consumed = HasInventory::shared_update(inventories, TestItems::ORE, 25);

  EXPECT_EQ(consumed, 25);
  EXPECT_EQ(agent1.inventory.amount(TestItems::ORE), 25);
}

TEST_F(MettaGridCppTest, SharedUpdate_AllInventoriesAtLimit) {
  // Test when all agent inventories are at their limit
  InventoryConfig inv_cfg;
  inv_cfg.limit_defs = {LimitDef({TestItems::ORE}, 10)};

  AgentConfig agent_cfg(1, "test_agent", 1, "test_group");
  agent_cfg.inventory_config = inv_cfg;

  auto resource_names = create_test_resource_names();
  Agent agent1(0, 0, agent_cfg, &resource_names);
  Agent agent2(1, 0, agent_cfg, &resource_names);

  // Fill both to limit
  agent1.inventory.update(TestItems::ORE, 10);
  agent2.inventory.update(TestItems::ORE, 10);

  std::vector<Inventory*> inventories = {&agent1.inventory, &agent2.inventory};

  // Try to add more
  InventoryDelta consumed = HasInventory::shared_update(inventories, TestItems::ORE, 20);

  EXPECT_EQ(consumed, 0);  // Nothing consumed since all at limit
  EXPECT_EQ(agent1.inventory.amount(TestItems::ORE), 10);
  EXPECT_EQ(agent2.inventory.amount(TestItems::ORE), 10);
}

TEST_F(MettaGridCppTest, SharedUpdate_MixedLimits) {
  // Test with agents having different inventory limits
  InventoryConfig inv_cfg1;
  inv_cfg1.limit_defs = {LimitDef({TestItems::ORE}, 10)};

  InventoryConfig inv_cfg2;
  inv_cfg2.limit_defs = {LimitDef({TestItems::ORE}, 20)};

  InventoryConfig inv_cfg3;
  inv_cfg3.limit_defs = {LimitDef({TestItems::ORE}, 30)};

  AgentConfig agent_cfg1(1, "test_agent1", 1, "test_group");
  agent_cfg1.inventory_config = inv_cfg1;

  AgentConfig agent_cfg2(2, "test_agent2", 1, "test_group");
  agent_cfg2.inventory_config = inv_cfg2;

  AgentConfig agent_cfg3(3, "test_agent3", 1, "test_group");
  agent_cfg3.inventory_config = inv_cfg3;

  auto resource_names = create_test_resource_names();
  Agent agent1(0, 0, agent_cfg1, &resource_names);  // Limit 10
  Agent agent2(1, 0, agent_cfg2, &resource_names);  // Limit 20
  Agent agent3(2, 0, agent_cfg3, &resource_names);  // Limit 30

  std::vector<Inventory*> inventories = {&agent1.inventory, &agent2.inventory, &agent3.inventory};

  // Try to add 45 ore
  // agent1 takes 10 (hits limit), agent2 takes 18, agent3 takes 17
  InventoryDelta consumed = HasInventory::shared_update(inventories, TestItems::ORE, 45);

  EXPECT_EQ(consumed, 45);
  EXPECT_EQ(agent1.inventory.amount(TestItems::ORE), 10);  // Hit limit
  EXPECT_EQ(agent2.inventory.amount(TestItems::ORE), 18);  // Gets more due to being earlier
  EXPECT_EQ(agent3.inventory.amount(TestItems::ORE), 17);
}
