#include <gtest/gtest.h>

#include <string>
#include <unordered_map>
#include <vector>

#include "config/observation_features.hpp"
#include "core/grid_object.hpp"
#include "objects/collective.hpp"
#include "objects/collective_config.hpp"

// Resource names for testing
static std::vector<std::string> test_resource_names = {"gold", "energy"};

// Test fixture for GridLocation class
class GridLocationTest : public ::testing::Test {
protected:
  void SetUp() override {
    // Setup code if needed before each test
  }

  void TearDown() override {
    // Cleanup code if needed after each test
  }
};

// Test default constructor
TEST_F(GridLocationTest, DefaultConstructor) {
  GridLocation location;
  EXPECT_EQ(0, location.r);
  EXPECT_EQ(0, location.c);
}

// Test two-parameter constructor
TEST_F(GridLocationTest, TwoParamConstructor) {
  GridLocation location(5, 10);
  EXPECT_EQ(5, location.r);
  EXPECT_EQ(10, location.c);
}

// Concrete implementation of GridObject for testing
class TestGridObject : public GridObject {
public:
  std::vector<PartialObservationToken> obs_features() const override {
    std::vector<PartialObservationToken> features;
    features.push_back({0, 1});
    return features;
  }
};

// Test fixture for GridObject
class GridObjectTest : public ::testing::Test {
protected:
  TestGridObject obj;

  void SetUp() override {
    // Reset object before each test if needed
  }
};

// Test init with GridLocation
TEST_F(GridObjectTest, InitWithLocation) {
  GridLocation loc(5, 10);
  std::vector<int> tags;  // Empty tags vector
  obj.init(1, "object", loc, tags);

  EXPECT_EQ(1, obj.type_id);
  EXPECT_EQ("object", obj.type_name);
  EXPECT_EQ(5, obj.location.r);
  EXPECT_EQ(10, obj.location.c);
}

// Test fixture for GridObject obs_features (uses base implementation)
class GridObjectObsFeaturesTest : public ::testing::Test {
protected:
  // Simple GridObject subclass that uses base obs_features()
  class SimpleGridObject : public GridObject {
  public:
    // Uses default base implementation for obs_features()
  };

  SimpleGridObject obj;

  void SetUp() override {
    // Initialize observation features
    std::unordered_map<std::string, ObservationType> feature_ids = {
        {"agent:group", 0},
        {"agent:frozen", 1},
        {"episode_completion_pct", 2},
        {"last_action", 3},
        {"last_reward", 4},
        {"goal", 5},
        {"vibe", 6},
        {"agent:compass", 7},
        {"tag", 8},
        {"cooldown_remaining", 9},
        {"remaining_uses", 10},
        {"collective", 11},
    };
    ObservationFeature::Initialize(feature_ids);
  }
};

// Test obs_features with no collective and no tags
TEST_F(GridObjectObsFeaturesTest, EmptyObsFeatures) {
  GridLocation loc(0, 0);
  std::vector<int> tags;  // Empty tags
  obj.init(1, "object", loc, tags);

  auto features = obj.obs_features();
  EXPECT_EQ(0, features.size());
}

// Test obs_features with tags only
TEST_F(GridObjectObsFeaturesTest, ObsFeaturesWithTags) {
  GridLocation loc(0, 0);
  std::vector<int> tags = {3, 5, 7};
  obj.init(1, "object", loc, tags);

  auto features = obj.obs_features();
  EXPECT_EQ(3, features.size());

  // All features should be tags
  for (size_t i = 0; i < features.size(); ++i) {
    EXPECT_EQ(ObservationFeature::Tag, features[i].feature_id);
    EXPECT_EQ(tags[i], features[i].value);
  }
}

// Test obs_features with collective only
TEST_F(GridObjectObsFeaturesTest, ObsFeaturesWithCollective) {
  GridLocation loc(0, 0);
  std::vector<int> tags;  // Empty tags
  obj.init(1, "object", loc, tags);

  // Create and set collective
  CollectiveConfig config;
  config.name = "test_collective";
  Collective collective(config, &test_resource_names);
  collective.id = 5;

  obj.setCollective(&collective);

  auto features = obj.obs_features();
  EXPECT_EQ(1, features.size());
  EXPECT_EQ(ObservationFeature::Collective, features[0].feature_id);
  EXPECT_EQ(5, features[0].value);
}

// Test obs_features with both collective and tags
TEST_F(GridObjectObsFeaturesTest, ObsFeaturesWithCollectiveAndTags) {
  GridLocation loc(0, 0);
  std::vector<int> tags = {10, 20};
  obj.init(1, "object", loc, tags);

  // Create and set collective
  CollectiveConfig config;
  config.name = "test_collective";
  Collective collective(config, &test_resource_names);
  collective.id = 3;

  obj.setCollective(&collective);

  auto features = obj.obs_features();
  EXPECT_EQ(3, features.size());  // 1 collective + 2 tags

  // First should be collective
  EXPECT_EQ(ObservationFeature::Collective, features[0].feature_id);
  EXPECT_EQ(3, features[0].value);

  // Rest should be tags
  EXPECT_EQ(ObservationFeature::Tag, features[1].feature_id);
  EXPECT_EQ(10, features[1].value);
  EXPECT_EQ(ObservationFeature::Tag, features[2].feature_id);
  EXPECT_EQ(20, features[2].value);
}
