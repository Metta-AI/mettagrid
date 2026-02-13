#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CONFIG_METTAGRID_CONFIG_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CONFIG_METTAGRID_CONFIG_HPP_

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <map>
#include <memory>
#include <string>
#include <unordered_map>
#include <vector>

#include "config/observation_features.hpp"
#include "core/game_value_config.hpp"
#include "core/query_config.hpp"
#include "core/types.hpp"
#include "handler/handler_config.hpp"
#include "objects/collective_config.hpp"

// Forward declarations
#include "actions/action_handler.hpp"
#include "core/grid_object.hpp"

using ObservationCoord = ObservationType;

// ObsValueConfig: a GameValueConfig + feature_id for observation emission.
// Replaces the old StatsValueConfig by using GameValueConfig which properly
// distinguishes INVENTORY vs STAT types and resolves them correctly.
struct ObsValueConfig {
  GameValueConfig value;
  ObservationType feature_id = 0;  // Pre-computed base feature ID
};

struct GlobalObsConfig {
  bool episode_completion_pct = true;
  bool last_action = true;
  bool last_reward = true;
  bool goal_obs = false;
  bool local_position = false;
  std::vector<ObsValueConfig> obs;
};

struct GameConfig {
  size_t num_agents;
  unsigned int max_steps;
  bool episode_truncates;
  ObservationCoord obs_width;
  ObservationCoord obs_height;
  std::vector<std::string> resource_names;
  std::vector<std::string> vibe_names;
  unsigned int num_observation_tokens;
  GlobalObsConfig global_obs;
  std::unordered_map<std::string, ObservationType> feature_ids;
  std::unordered_map<std::string, std::shared_ptr<ActionConfig>> actions;
  std::unordered_map<std::string, std::shared_ptr<GridObjectConfig>> objects;
  std::unordered_map<int, std::string> tag_id_map;

  // Collective configurations - maps collective name to config
  std::unordered_map<std::string, std::shared_ptr<CollectiveConfig>> collectives;

  // FEATURE FLAGS
  bool protocol_details_obs = true;
  std::unordered_map<std::string, float> reward_estimates = {};

  // Observation encoding settings
  unsigned int token_value_base = 256;  // Base for multi-token inventory encoding (value per token: 0 to base-1)

  // Events - timestep-triggered effects that apply mutations to filtered objects
  std::map<std::string, mettagrid::EventConfig> events;

  // Query tags - computed tag membership from spatial queries
  std::vector<mettagrid::QueryTagConfig> query_tags;
};

namespace py = pybind11;

inline void bind_obs_value_config(py::module& m) {
  py::class_<ObsValueConfig>(m, "ObsValueConfig")
      .def(py::init<>())
      .def_readwrite("value", &ObsValueConfig::value)
      .def_readwrite("feature_id", &ObsValueConfig::feature_id);
}

inline void bind_global_obs_config(py::module& m) {
  py::class_<GlobalObsConfig>(m, "GlobalObsConfig")
      .def(py::init<>())
      .def(py::init<bool, bool, bool, bool, bool, std::vector<ObsValueConfig>>(),
           py::arg("episode_completion_pct") = true,
           py::arg("last_action") = true,
           py::arg("last_reward") = true,
           py::arg("goal_obs") = false,
           py::arg("local_position") = false,
           py::arg("obs") = std::vector<ObsValueConfig>())
      .def_readwrite("episode_completion_pct", &GlobalObsConfig::episode_completion_pct)
      .def_readwrite("last_action", &GlobalObsConfig::last_action)
      .def_readwrite("last_reward", &GlobalObsConfig::last_reward)
      .def_readwrite("goal_obs", &GlobalObsConfig::goal_obs)
      .def_readwrite("local_position", &GlobalObsConfig::local_position)
      .def_readwrite("obs", &GlobalObsConfig::obs);
}

inline void bind_query_config(py::module& m) {
  using namespace mettagrid;

  py::enum_<QueryOrderBy>(m, "QueryOrderBy").value("none", QueryOrderBy::none).value("random", QueryOrderBy::random);

  py::class_<TagQueryConfig>(m, "TagQueryConfig")
      .def(py::init<>())
      .def_readwrite("tag_id", &TagQueryConfig::tag_id)
      .def_readwrite("max_items", &TagQueryConfig::max_items)
      .def_readwrite("order_by", &TagQueryConfig::order_by)
      .def(
          "add_tag_filter",
          [](TagQueryConfig& self, const TagFilterConfig& cfg) { self.filters.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_vibe_filter",
          [](TagQueryConfig& self, const VibeFilterConfig& cfg) { self.filters.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_resource_filter",
          [](TagQueryConfig& self, const ResourceFilterConfig& cfg) { self.filters.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_max_distance_filter",
          [](TagQueryConfig& self, const MaxDistanceFilterConfig& cfg) { self.filters.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_neg_filter",
          [](TagQueryConfig& self, const NegFilterConfig& cfg) { self.filters.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_or_filter",
          [](TagQueryConfig& self, const OrFilterConfig& cfg) { self.filters.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_game_value_filter",
          [](TagQueryConfig& self, const GameValueFilterConfig& cfg) { self.filters.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_shared_tag_prefix_filter",
          [](TagQueryConfig& self, const SharedTagPrefixFilterConfig& cfg) { self.filters.push_back(cfg); },
          py::arg("filter"));

  py::class_<ClosureQueryConfig>(m, "ClosureQueryConfig")
      .def(py::init<>())
      .def_readwrite("radius", &ClosureQueryConfig::radius)
      .def_readwrite("max_items", &ClosureQueryConfig::max_items)
      .def_readwrite("order_by", &ClosureQueryConfig::order_by)
      .def(
          "set_source",
          [](ClosureQueryConfig& self, const QueryConfigHolder& src) { self.source = src.config; },
          py::arg("source"))
      .def(
          "add_tag_filter",
          [](ClosureQueryConfig& self, const TagFilterConfig& cfg) { self.edge_filter.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_shared_tag_prefix_filter",
          [](ClosureQueryConfig& self, const SharedTagPrefixFilterConfig& cfg) { self.edge_filter.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_neg_filter",
          [](ClosureQueryConfig& self, const NegFilterConfig& cfg) { self.edge_filter.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_or_filter",
          [](ClosureQueryConfig& self, const OrFilterConfig& cfg) { self.edge_filter.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_max_distance_filter",
          [](ClosureQueryConfig& self, const MaxDistanceFilterConfig& cfg) { self.edge_filter.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_resource_filter",
          [](ClosureQueryConfig& self, const ResourceFilterConfig& cfg) { self.edge_filter.push_back(cfg); },
          py::arg("filter"))
      .def(
          "add_game_value_filter",
          [](ClosureQueryConfig& self, const GameValueFilterConfig& cfg) { self.edge_filter.push_back(cfg); },
          py::arg("filter"));

  py::class_<MaxDistanceFilterConfig>(m, "MaxDistanceFilterConfig")
      .def(py::init<>())
      .def_readwrite("entity", &MaxDistanceFilterConfig::entity)
      .def_readwrite("radius", &MaxDistanceFilterConfig::radius)
      .def(
          "set_source",
          [](MaxDistanceFilterConfig& self, const QueryConfigHolder& src) { self.source = src.config; },
          py::arg("source"));

  py::class_<QueryConfigHolder>(m, "QueryConfigHolder").def(py::init<>());

  m.def("make_query_config",
        [](const TagQueryConfig& q) { return QueryConfigHolder{std::make_shared<TagQueryConfig>(q)}; });
  m.def("make_query_config",
        [](const ClosureQueryConfig& q) { return QueryConfigHolder{std::make_shared<ClosureQueryConfig>(q)}; });

  py::class_<QueryTagConfig>(m, "QueryTagConfig")
      .def(py::init<>())
      .def_readwrite("tag_id", &QueryTagConfig::tag_id)
      .def(
          "set_query",
          [](QueryTagConfig& self, const QueryConfigHolder& q) { self.query = q.config; },
          py::arg("query"));

  py::class_<RecomputeQueryTagMutationConfig>(m, "RecomputeQueryTagMutationConfig")
      .def(py::init<>())
      .def_readwrite("tag_id", &RecomputeQueryTagMutationConfig::tag_id);
}

inline void bind_game_config(py::module& m) {
  py::class_<GameConfig>(m, "GameConfig")
      .def(py::init<unsigned int,
                    unsigned int,
                    bool,
                    ObservationCoord,
                    ObservationCoord,
                    const std::vector<std::string>&,
                    const std::vector<std::string>&,
                    unsigned int,
                    const GlobalObsConfig&,
                    const std::unordered_map<std::string, ObservationType>&,
                    const std::unordered_map<std::string, std::shared_ptr<ActionConfig>>&,
                    const std::unordered_map<std::string, std::shared_ptr<GridObjectConfig>>&,
                    const std::unordered_map<int, std::string>&,

                    // Collectives
                    const std::unordered_map<std::string, std::shared_ptr<CollectiveConfig>>&,

                    // FEATURE FLAGS
                    bool,
                    const std::unordered_map<std::string, float>&,

                    // Observation encoding
                    unsigned int,

                    // Events
                    const std::map<std::string, mettagrid::EventConfig>&,

                    // Query tags
                    const std::vector<mettagrid::QueryTagConfig>&>(),
           py::arg("num_agents"),
           py::arg("max_steps"),
           py::arg("episode_truncates"),
           py::arg("obs_width"),
           py::arg("obs_height"),
           py::arg("resource_names"),
           py::arg("vibe_names"),
           py::arg("num_observation_tokens"),
           py::arg("global_obs"),
           py::arg("feature_ids"),
           py::arg("actions"),
           py::arg("objects"),
           py::arg("tag_id_map") = std::unordered_map<int, std::string>(),

           // Collectives
           py::arg("collectives") = std::unordered_map<std::string, std::shared_ptr<CollectiveConfig>>(),

           // FEATURE FLAGS
           py::arg("protocol_details_obs") = true,
           py::arg("reward_estimates") = std::unordered_map<std::string, float>(),

           // Observation encoding
           py::arg("token_value_base") = 256,

           // Events
           py::arg("events") = std::map<std::string, mettagrid::EventConfig>(),

           // Query tags
           py::arg("query_tags") = std::vector<mettagrid::QueryTagConfig>())
      .def_readwrite("num_agents", &GameConfig::num_agents)
      .def_readwrite("max_steps", &GameConfig::max_steps)
      .def_readwrite("episode_truncates", &GameConfig::episode_truncates)
      .def_readwrite("obs_width", &GameConfig::obs_width)
      .def_readwrite("obs_height", &GameConfig::obs_height)
      .def_readwrite("resource_names", &GameConfig::resource_names)
      .def_readwrite("vibe_names", &GameConfig::vibe_names)
      .def_readwrite("num_observation_tokens", &GameConfig::num_observation_tokens)
      .def_readwrite("global_obs", &GameConfig::global_obs)
      .def_readwrite("feature_ids", &GameConfig::feature_ids)

      // We don't expose these since they're copied on read, and this means that mutations
      // to the dictionaries don't impact the underlying cpp objects. This is confusing!
      // This can be fixed, but until we do that, we're not exposing these.
      // .def_readwrite("actions", &GameConfig::actions)
      // .def_readwrite("objects", &GameConfig::objects);

      .def_readwrite("tag_id_map", &GameConfig::tag_id_map)

      // Collectives
      .def_readwrite("collectives", &GameConfig::collectives)

      // FEATURE FLAGS
      .def_readwrite("protocol_details_obs", &GameConfig::protocol_details_obs)
      .def_readwrite("reward_estimates", &GameConfig::reward_estimates)

      // Observation encoding
      .def_readwrite("token_value_base", &GameConfig::token_value_base)

      // Events
      .def_readwrite("events", &GameConfig::events)

      // Query tags
      .def_readwrite("query_tags", &GameConfig::query_tags);
}

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CONFIG_METTAGRID_CONFIG_HPP_
