#include "bindings/mettagrid_c.hpp"

#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <random>
#include <string>
#include <type_traits>
#include <unordered_set>
#include <vector>

#include "actions/action_handler.hpp"
#include "actions/action_handler_factory.hpp"
#include "actions/attack.hpp"
#include "actions/change_vibe.hpp"
#include "actions/move_config.hpp"
#include "config/observation_features.hpp"
#include "core/grid.hpp"
#include "core/grid_object_factory.hpp"
#include "core/types.hpp"
#include "handler/handler_bindings.hpp"
#include "handler/handler_context.hpp"
#include "objects/agent.hpp"
#include "objects/alignable.hpp"
#include "objects/collective.hpp"
#include "objects/collective_config.hpp"
#include "objects/constants.hpp"
#include "objects/inventory_config.hpp"
#include "objects/protocol.hpp"
#include "objects/wall.hpp"
#include "systems/observation_encoder.hpp"
#include "systems/packed_coordinate.hpp"
#include "systems/stats_tracker.hpp"

namespace py = pybind11;

MettaGrid::MettaGrid(const GameConfig& game_config, const py::list map, unsigned int seed)
    : obs_width(game_config.obs_width),
      obs_height(game_config.obs_height),
      max_steps(game_config.max_steps),
      episode_truncates(game_config.episode_truncates),
      resource_names(game_config.resource_names),
      _global_obs_config(game_config.global_obs),
      _game_config(game_config),
      _num_observation_tokens(game_config.num_observation_tokens) {
  _seed = seed;
  _rng = std::mt19937(seed);

  const char* profiling_env = std::getenv("METTAGRID_PROFILING");
  _profiling_enabled = profiling_env && std::string(profiling_env) == "1";

  // `map` is a list of lists of strings, which are the map cells.

  unsigned int num_agents = static_cast<unsigned int>(game_config.num_agents);

  current_step = 0;

  bool observation_size_is_packable =
      obs_width <= PackedCoordinate::MAX_PACKABLE_COORD + 1 && obs_height <= PackedCoordinate::MAX_PACKABLE_COORD + 1;
  if (!observation_size_is_packable) {
    throw std::runtime_error("Observation window size (" + std::to_string(obs_width) + "x" +
                             std::to_string(obs_height) + ") exceeds maximum packable size");
  }

  // Pre-compute observation pattern offsets (Manhattan distance order)
  _observation_offsets.reserve(static_cast<size_t>(obs_height) * static_cast<size_t>(obs_width));
  for (const auto& offset : PackedCoordinate::ObservationPattern{obs_height, obs_width}) {
    _observation_offsets.push_back(offset);
  }

  // Reserve capacity for global tokens buffer (reused per agent to avoid allocation).
  // Breakdown: episode_completion(1) + last_action(1) + last_reward(1) + goal_tokens(N) +
  // local_position(up to 2) + obs_value_tokens(varies). 32 covers typical configs with margin.
  _global_tokens_buffer.reserve(32);

  // Compute max scratch buffer size from config
  {
    size_t max_tags = game_config.tag_id_map.size();
    size_t num_resources = resource_names.size();
    size_t tokens_per_item = ObservationEncoder::compute_num_tokens(65535, game_config.token_value_base);
    _obs_features_scratch.resize(Agent::max_obs_features(max_tags, num_resources, tokens_per_item));
  }

  GridCoord height = static_cast<GridCoord>(py::len(map));
  GridCoord width = static_cast<GridCoord>(py::len(map[0]));

  _grid = std::make_unique<Grid>(height, width);
  _aoe_tracker = std::make_unique<mettagrid::AOETracker>(height, width, nullptr, &_tag_index);
  _obs_encoder = std::make_unique<ObservationEncoder>(
      game_config.protocol_details_obs, resource_names, game_config.feature_ids, game_config.token_value_base);

  // Initialize ObservationFeature namespace with feature IDs
  ObservationFeature::Initialize(game_config.feature_ids);

  // Initialize feature_id_to_name map from GameConfig
  for (const auto& [name, id] : game_config.feature_ids) {
    feature_id_to_name[id] = name;
  }

  _stats = std::make_unique<StatsTracker>(&resource_names);

  // Pre-resolve stat IDs for hot-path observation stats (avoids string hashing per agent per step)
  _stat_tokens_written = _stats->get_or_create_id("tokens_written");
  _stat_tokens_dropped = _stats->get_or_create_id("tokens_dropped");
  _stat_tokens_free_space = _stats->get_or_create_id("tokens_free_space");
  _aoe_tracker->set_game_stats(_stats.get());
  _token_encoder = std::make_unique<ObservationTokenEncoder>(_game_config.token_value_base);

  _action_success.resize(num_agents);

  init_action_handlers();

  // Initialize collectives from config in SORTED order (before _init_grid so objects can reference them)
  // This ensures collective IDs match between Python and C++ (unordered_map iteration is unpredictable)
  std::vector<std::string> collective_names;
  collective_names.reserve(game_config.collectives.size());
  for (const auto& [name, _] : game_config.collectives) {
    collective_names.push_back(name);
  }
  std::sort(collective_names.begin(), collective_names.end());

  for (const auto& name : collective_names) {
    const auto& collective_cfg = game_config.collectives.at(name);
    auto collective = std::make_unique<Collective>(*collective_cfg, &resource_names);
    collective->id = static_cast<int>(_collectives.size());  // Set ID to index (sorted order)
    _collectives_by_name[name] = collective.get();
    _collectives_by_id.push_back(collective.get());
    _collectives.push_back(std::move(collective));
  }

  // Set collectives on AOETracker for alignment filter lookups (before _init_grid registers AOE sources)
  _aoe_tracker->set_collectives(&_collectives);

  _init_grid(game_config, map, _collectives_by_id);

  _prev_agent_locations.resize(_agents.size());
  for (size_t i = 0; i < _agents.size(); ++i) {
    _prev_agent_locations[i] = _agents[i]->location;
  }

  // Initialize QuerySystem — always created so inline queries in filters/mutations work
  _query_system = std::make_unique<mettagrid::QuerySystem>(_grid.get(), &_tag_index, &_rng, game_config.query_tags);
  _aoe_tracker->set_query_system(_query_system.get());
  _query_system->compute_all();

  // Initialize EventScheduler from config
  if (!game_config.events.empty()) {
    _event_scheduler = std::make_unique<mettagrid::EventScheduler>(game_config.events, &_rng);
    _event_scheduler->set_collectives(&_collectives);
    _event_scheduler->set_grid(_grid.get());
  }

  // Pre-compute goal_obs tokens for each agent
  if (_global_obs_config.goal_obs) {
    _agent_goal_obs_tokens.resize(_agents.size());
    for (size_t i = 0; i < _agents.size(); i++) {
      _compute_agent_goal_obs_tokens(i);
    }
  }

  // Initialize reward entries (resolve stat names to IDs, get pointers)
  for (auto* agent : _agents) {
    Collective* coll = agent->getCollective();
    StatsTracker* collective_stats = coll ? &coll->stats : nullptr;
    agent->init_reward(collective_stats, _stats.get(), &_tag_index, _query_system.get(), &resource_names);
  }

  // Validation configuration from environment variables
  if (const char* val = std::getenv("METTAGRID_OBS_VALIDATION")) {
    _validation_enabled = (std::string(val) == "1");
  }
  _use_optimized_primary = true;
  if (const char* val = std::getenv("METTAGRID_OBS_USE_OPTIMIZED")) {
    _use_optimized_primary = (std::string(val) == "1");
  }

  if (_validation_enabled) {
    std::cerr << "[METTAGRID OBS_VALIDATION] ENABLED, primary=" << (_use_optimized_primary ? "optimized" : "original")
              << std::endl;
  }

  // Create buffers
  _make_buffers(num_agents);
}

MettaGrid::~MettaGrid() = default;

void MettaGrid::_init_grid(const GameConfig& game_config,
                           const py::list& map,
                           const std::vector<Collective*>& collectives_by_id) {
  GridCoord height = static_cast<GridCoord>(py::len(map));
  GridCoord width = static_cast<GridCoord>(py::len(map[0]));

  object_type_names.resize(game_config.objects.size());

  for (const auto& [key, object_cfg] : game_config.objects) {
    TypeId type_id = object_cfg->type_id;

    if (type_id >= object_type_names.size()) {
      // Sometimes the type_ids are not contiguous, so we need to resize the vector.
      object_type_names.resize(type_id + 1);
    }

    if (object_type_names[type_id] != "" && object_type_names[type_id] != object_cfg->type_name) {
      throw std::runtime_error("Object type_id " + std::to_string(type_id) + " already exists with type_name " +
                               object_type_names[type_id] + ". Trying to add " + object_cfg->type_name + ".");
    }
    object_type_names[type_id] = object_cfg->type_name;
  }

  // Initialize objects from map
  for (GridCoord r = 0; r < height; r++) {
    for (GridCoord c = 0; c < width; c++) {
      auto py_cell = map[r].cast<py::list>()[c].cast<py::str>();
      auto cell = py_cell.cast<std::string>();

      // #HardCodedConfig
      if (cell == "empty" || cell == "." || cell == " ") {
        continue;
      }

      if (!game_config.objects.contains(cell)) {
        throw std::runtime_error("Unknown object type: " + cell);
      }

      const GridObjectConfig* object_cfg = game_config.objects.at(cell).get();

      // Create object from config using the factory
      GridObject* created_object = mettagrid::create_object_from_config(r,
                                                                        c,
                                                                        object_cfg,
                                                                        _stats.get(),
                                                                        &resource_names,
                                                                        _grid.get(),
                                                                        _obs_encoder.get(),
                                                                        &current_step,
                                                                        &_tag_index,
                                                                        &collectives_by_id);

      // Add to grid and track stats
      _grid->add_object(created_object);
      _stats->incr("objects." + cell);

      // Wire up grid, tag index, and register the object
      created_object->set_grid(_grid.get());
      created_object->set_tag_index(&_tag_index);
      _tag_index.register_object(created_object);

      // Register AOE configs for this object (possibly none)
      for (const auto& aoe_config : created_object->aoe_configs()) {
        _aoe_tracker->register_source(*created_object, aoe_config);
      }

      // Handle agent-specific setup (agent_id and registration)
      if (Agent* agent = dynamic_cast<Agent*>(created_object)) {
        if (_agents.size() > std::numeric_limits<decltype(agent->agent_id)>::max()) {
          throw std::runtime_error("Too many agents for agent_id type");
        }
        agent->agent_id = static_cast<decltype(agent->agent_id)>(_agents.size());
        add_agent(agent);
      }
    }
  }
}

void MettaGrid::_make_buffers(unsigned int num_agents) {
  // Create and set buffers
  std::vector<ssize_t> shape;
  shape = {static_cast<ssize_t>(num_agents), static_cast<ssize_t>(_num_observation_tokens), static_cast<ssize_t>(3)};
  auto observations = py::array_t<ObservationType, py::array::c_style>(shape);
  auto terminals =
      py::array_t<TerminalType, py::array::c_style>({static_cast<ssize_t>(num_agents)}, {sizeof(TerminalType)});
  auto truncations =
      py::array_t<TruncationType, py::array::c_style>({static_cast<ssize_t>(num_agents)}, {sizeof(TruncationType)});
  auto rewards = py::array_t<RewardType, py::array::c_style>({static_cast<ssize_t>(num_agents)}, {sizeof(RewardType)});
  auto actions = py::array_t<ActionType, py::array::c_style>(std::vector<ssize_t>{static_cast<ssize_t>(num_agents)});
  this->_episode_rewards =
      py::array_t<float, py::array::c_style>({static_cast<ssize_t>(num_agents)}, {sizeof(RewardType)});

  set_buffers(observations, terminals, truncations, rewards, actions);
}

void MettaGrid::_init_buffers(unsigned int num_agents) {
  assert(current_step == 0 && "current_step should be initialized to 0 at the start of _init_buffers");

  // Clear all buffers
  std::fill(static_cast<bool*>(_terminals.request().ptr),
            static_cast<bool*>(_terminals.request().ptr) + _terminals.size(),
            0);
  std::fill(static_cast<bool*>(_truncations.request().ptr),
            static_cast<bool*>(_truncations.request().ptr) + _truncations.size(),
            0);
  std::fill(static_cast<float*>(_episode_rewards.request().ptr),
            static_cast<float*>(_episode_rewards.request().ptr) + _episode_rewards.size(),
            0.0f);
  std::fill(
      static_cast<float*>(_rewards.request().ptr), static_cast<float*>(_rewards.request().ptr) + _rewards.size(), 0.0f);

  // Clear observations
  auto obs_ptr = static_cast<uint8_t*>(_observations.request().ptr);
  auto obs_size = _observations.size();
  std::fill(obs_ptr, obs_ptr + obs_size, EmptyTokenByte);

  // Compute initial observations. Every agent starts with a noop.
  std::vector<ActionType> executed_actions(_agents.size());
  std::fill(executed_actions.begin(), executed_actions.end(), ActionType(0));
  _compute_observations(executed_actions);
}

void MettaGrid::init_action_handlers() {
  auto result = create_action_handlers(_game_config, _grid.get(), &_rng);
  _max_action_priority = result.max_priority;
  _action_handlers = std::move(result.actions);
  _action_handler_impl = std::move(result.handlers);
}

void MettaGrid::add_agent(Agent* agent) {
  agent->init(&_rewards.mutable_unchecked<1>()(_agents.size()));
  _agents.push_back(agent);
  if (_global_obs_config.goal_obs) {
    _agent_goal_obs_tokens.resize(_agents.size());
    _compute_agent_goal_obs_tokens(_agents.size() - 1);
  }
}

void MettaGrid::_compute_agent_goal_obs_tokens(size_t agent_idx) {
  auto& agent = _agents[agent_idx];
  std::vector<PartialObservationToken> goal_tokens;

  // Track which resources we've already added goal tokens for
  std::unordered_set<std::string> added_resources;

  // Helper to add a goal token for a resource name
  auto add_resource_goal = [&](const std::string& resource_name) {
    if (added_resources.find(resource_name) != added_resources.end()) return;  // already added
    for (size_t i = 0; i < resource_names.size(); i++) {
      if (resource_names[i] == resource_name) {
        ObservationType inventory_feature_id = _obs_encoder->get_inventory_feature_id(static_cast<InventoryItem>(i));
        goal_tokens.push_back({ObservationFeature::Goal, inventory_feature_id});
        added_resources.insert(resource_name);
        break;
      }
    }
  };

  // Extract resource info from reward entries for goal observation tokens
  for (const auto& entry : agent->reward_helper.config.entries) {
    std::visit(
        [&](auto&& c) {
          using T = std::decay_t<decltype(c)>;
          if constexpr (std::is_same_v<T, InventoryValueConfig>) {
            if (c.id < resource_names.size()) {
              add_resource_goal(resource_names[c.id]);
            }
          }
        },
        entry.numerator);
  }

  _agent_goal_obs_tokens[agent_idx] = std::move(goal_tokens);
}

void MettaGrid::_emit_tile_observability_tokens(size_t agent_idx,
                                                const GridLocation& object_loc,
                                                uint8_t location,
                                                ObservationToken*& obs_ptr,
                                                size_t& tokens_written,
                                                size_t& attempted_tokens_written,
                                                size_t buffer_capacity) {
  ObservationType aoe_mask = 0;
  ObservationType territory = 0;
  ObservationType* aoe_mask_ptr = (ObservationFeature::AoeMask != 0) ? &aoe_mask : nullptr;
  ObservationType* territory_ptr = (ObservationFeature::Territory != 0) ? &territory : nullptr;
  if (aoe_mask_ptr == nullptr && territory_ptr == nullptr) {
    return;
  }

  _aoe_tracker->fixed_observability_at(object_loc, *_agents[agent_idx], aoe_mask_ptr, territory_ptr);

  if (aoe_mask != 0) {
    attempted_tokens_written += 1;
    if (tokens_written < buffer_capacity) {
      obs_ptr[0].location = location;
      obs_ptr[0].feature_id = ObservationFeature::AoeMask;
      obs_ptr[0].value = aoe_mask;
      obs_ptr += 1;
      tokens_written += 1;
    }
  }

  if (territory != 0) {
    attempted_tokens_written += 1;
    if (tokens_written < buffer_capacity) {
      obs_ptr[0].location = location;
      obs_ptr[0].feature_id = ObservationFeature::Territory;
      obs_ptr[0].value = territory;
      obs_ptr += 1;
      tokens_written += 1;
    }
  }
}

// Dispatcher: routes to original or optimized based on validation config
void MettaGrid::_compute_observation(GridCoord observer_row,
                                     GridCoord observer_col,
                                     ObservationCoord observable_width,
                                     ObservationCoord observable_height,
                                     size_t agent_idx,
                                     ActionType action) {
  if (_use_optimized_primary) {
    if (_validation_enabled) {
      auto start = std::chrono::steady_clock::now();
      _compute_observation_optimized(
          observer_row, observer_col, observable_width, observable_height, agent_idx, action);
      auto end = std::chrono::steady_clock::now();
      double elapsed_ns = std::chrono::duration<double, std::nano>(end - start).count();
      _shadow_validate_observation(
          observer_row, observer_col, observable_width, observable_height, agent_idx, action, elapsed_ns, true);
    } else {
      _compute_observation_optimized(
          observer_row, observer_col, observable_width, observable_height, agent_idx, action);
    }
  } else {
    if (_validation_enabled) {
      auto start = std::chrono::steady_clock::now();
      _compute_observation_original(observer_row, observer_col, observable_width, observable_height, agent_idx, action);
      auto end = std::chrono::steady_clock::now();
      double elapsed_ns = std::chrono::duration<double, std::nano>(end - start).count();
      _shadow_validate_observation(
          observer_row, observer_col, observable_width, observable_height, agent_idx, action, elapsed_ns, false);
    } else {
      _compute_observation_original(observer_row, observer_col, observable_width, observable_height, agent_idx, action);
    }
  }
}

// Shadow validation: runs the other path and compares outputs
void MettaGrid::_shadow_validate_observation(GridCoord observer_row,
                                             GridCoord observer_col,
                                             ObservationCoord observable_width,
                                             ObservationCoord observable_height,
                                             size_t agent_idx,
                                             ActionType action,
                                             double primary_time_ns,
                                             bool primary_was_optimized) {
  auto observation_view = _observations.mutable_unchecked<3>();
  size_t num_tokens = static_cast<size_t>(observation_view.shape(1));
  size_t token_size = static_cast<size_t>(observation_view.shape(2));
  size_t agent_obs_size = num_tokens * token_size;

  // Ensure shadow buffer is sized correctly
  if (_shadow_obs_buffer.size() < agent_obs_size) {
    _shadow_obs_buffer.resize(agent_obs_size);
  }

  // Save current observation to shadow buffer
  ObservationType* primary_obs = observation_view.mutable_data(agent_idx, 0, 0);
  std::copy(primary_obs, primary_obs + agent_obs_size, _shadow_obs_buffer.begin());

  // Clear observation buffer and run secondary path.
  // NOTE: This temporarily corrupts the agent's observation buffer. Safe only because
  // observations are computed sequentially per agent (no concurrent readers).
  std::fill(primary_obs, primary_obs + agent_obs_size, EmptyTokenByte);

  auto start = std::chrono::steady_clock::now();
  if (primary_was_optimized) {
    _compute_observation_original(observer_row, observer_col, observable_width, observable_height, agent_idx, action);
  } else {
    _compute_observation_optimized(observer_row, observer_col, observable_width, observable_height, agent_idx, action);
  }
  auto end = std::chrono::steady_clock::now();
  double secondary_time_ns = std::chrono::duration<double, std::nano>(end - start).count();

  // Compare outputs
  bool mismatch = false;
  size_t first_mismatch_idx = 0;
  for (size_t i = 0; i < agent_obs_size; ++i) {
    if (_shadow_obs_buffer[i] != primary_obs[i]) {
      mismatch = true;
      first_mismatch_idx = i;
      break;
    }
  }

  // Update stats
  _obs_validation_stats.comparison_count++;
  if (mismatch) {
    _obs_validation_stats.mismatch_count++;
    // Log first few mismatches for debugging
    if (_obs_validation_stats.mismatch_count <= 10) {
      size_t token_idx = first_mismatch_idx / token_size;
      size_t component = first_mismatch_idx % token_size;
      const char* component_names[] = {"location", "feature_id", "value"};
      std::cerr << "[METTAGRID OBS_VALIDATION] Mismatch at agent " << agent_idx << " token " << token_idx << " "
                << component_names[component]
                << ": primary=" << static_cast<int>(_shadow_obs_buffer[first_mismatch_idx])
                << " secondary=" << static_cast<int>(primary_obs[first_mismatch_idx]) << std::endl;
    }
  }

  // Accumulate timing
  if (primary_was_optimized) {
    _obs_validation_stats.optimized_time_ns += primary_time_ns;
    _obs_validation_stats.original_time_ns += secondary_time_ns;
  } else {
    _obs_validation_stats.original_time_ns += primary_time_ns;
    _obs_validation_stats.optimized_time_ns += secondary_time_ns;
  }

  // Periodic timing ratio log for production monitoring
  // Tiered reporting: early data at 1K and 10K, then every 100K
  auto count = _obs_validation_stats.comparison_count;
  if (count == 1000 || count == 10000 || (count >= 100000 && count % 100000 == 0)) {
    double ratio = _obs_validation_stats.original_time_ns / std::max(_obs_validation_stats.optimized_time_ns, 1.0);
    std::cerr << "[METTAGRID OBS_VALIDATION] " << _obs_validation_stats.comparison_count << " comparisons, "
              << _obs_validation_stats.mismatch_count << " mismatches, "
              << "timing ratio=" << std::fixed << std::setprecision(2) << ratio << "x" << std::endl;
  }

  // Restore primary observation (the one we want to keep)
  std::copy(_shadow_obs_buffer.begin(), _shadow_obs_buffer.begin() + agent_obs_size, primary_obs);
}

// Original path: matches main branch behavior exactly
void MettaGrid::_compute_observation_original(GridCoord observer_row,
                                              GridCoord observer_col,
                                              ObservationCoord observable_width,
                                              ObservationCoord observable_height,
                                              size_t agent_idx,
                                              ActionType action) {
  // Calculate observation boundaries
  ObservationCoord obs_width_radius = observable_width >> 1;
  ObservationCoord obs_height_radius = observable_height >> 1;

  int r_start = std::max(static_cast<int>(observer_row) - static_cast<int>(obs_height_radius), 0);
  int c_start = std::max(static_cast<int>(observer_col) - static_cast<int>(obs_width_radius), 0);

  int r_end = std::min(static_cast<int>(observer_row) + static_cast<int>(obs_height_radius) + 1,
                       static_cast<int>(_grid->height));
  int c_end =
      std::min(static_cast<int>(observer_col) + static_cast<int>(obs_width_radius) + 1, static_cast<int>(_grid->width));

  // Fill in visible objects. Observations should have been cleared in _step, so
  // we don't need to do that here.
  size_t attempted_tokens_written = 0;
  size_t tokens_written = 0;
  auto observation_view = _observations.mutable_unchecked<3>();
  auto rewards_view = _rewards.unchecked<1>();

  // Global tokens
  ObservationToken* agent_obs_ptr = reinterpret_cast<ObservationToken*>(observation_view.mutable_data(agent_idx, 0, 0));
  ObservationTokens agent_obs_tokens(
      agent_obs_ptr, static_cast<size_t>(observation_view.shape(1)) - static_cast<size_t>(tokens_written));

  auto& global_tokens = _global_tokens_buffer;
  global_tokens.clear();

  if (_global_obs_config.episode_completion_pct) {
    ObservationType episode_completion_pct = 0;
    if (max_steps > 0) {
      if (current_step >= max_steps) {
        episode_completion_pct = std::numeric_limits<ObservationType>::max();
      } else {
        episode_completion_pct = static_cast<ObservationType>(
            (static_cast<uint32_t>(std::numeric_limits<ObservationType>::max()) + 1) * current_step / max_steps);
      }
    }
    global_tokens.push_back({ObservationFeature::EpisodeCompletionPct, episode_completion_pct});
  }

  if (_global_obs_config.last_action) {
    global_tokens.push_back({ObservationFeature::LastAction, static_cast<ObservationType>(action)});
  }

  if (ObservationFeature::LastActionMove != 0) {
    bool moved = !(_agents[agent_idx]->location == _prev_agent_locations[agent_idx]);
    global_tokens.push_back({ObservationFeature::LastActionMove, static_cast<ObservationType>(moved ? 1 : 0)});
  }

  if (_global_obs_config.last_reward) {
    RewardType reward = rewards_view(agent_idx);
    ObservationType reward_int = static_cast<ObservationType>(std::round(reward * 100.0f));
    global_tokens.push_back({ObservationFeature::LastReward, reward_int});
  }

  if (_global_obs_config.goal_obs) {
    global_tokens.insert(global_tokens.end(), _agent_goal_obs_tokens[agent_idx].begin(), _agent_goal_obs_tokens[agent_idx].end());
  }

  if (_global_obs_config.local_position) {
    auto& agent = *_agents[agent_idx];
    int dc = static_cast<int>(agent.location.c) - static_cast<int>(agent.spawn_location.c);
    int dr = static_cast<int>(agent.spawn_location.r) - static_cast<int>(agent.location.r);
    if (dc > 0) {
      global_tokens.push_back({ObservationFeature::LpEast, static_cast<ObservationType>(std::min(dc, 255))});
    } else if (dc < 0) {
      global_tokens.push_back({ObservationFeature::LpWest, static_cast<ObservationType>(std::min(-dc, 255))});
    }
    if (dr > 0) {
      global_tokens.push_back({ObservationFeature::LpNorth, static_cast<ObservationType>(std::min(dr, 255))});
    } else if (dr < 0) {
      global_tokens.push_back({ObservationFeature::LpSouth, static_cast<ObservationType>(std::min(-dr, 255))});
    }
  }

  // Global tokens use a dedicated location marker (0xFE) distinct from spatial coordinates.
  uint8_t global_location = PackedCoordinate::GLOBAL_LOCATION;

  attempted_tokens_written +=
      _obs_encoder->append_tokens_if_room_available(agent_obs_tokens, global_tokens, global_location);
  tokens_written = std::min(attempted_tokens_written, static_cast<size_t>(observation_view.shape(1)));

  // Emit obs tokens - resolve each GameValueConfig inline
  attempted_tokens_written += _emit_obs_value_tokens(agent_idx, tokens_written, global_location);
  tokens_written = std::min(attempted_tokens_written, static_cast<size_t>(observation_view.shape(1)));

  // Process locations in increasing manhattan distance order
  for (const auto& [r_offset, c_offset] : PackedCoordinate::ObservationPattern{observable_height, observable_width}) {
    int r = static_cast<int>(observer_row) + r_offset;
    int c = static_cast<int>(observer_col) + c_offset;

    // Skip if outside map bounds
    if (r < r_start || r >= r_end || c < c_start || c >= c_end) {
      continue;
    }

    // Process a single grid location
    GridLocation object_loc(static_cast<GridCoord>(r), static_cast<GridCoord>(c));
    auto obj = _grid->object_at(object_loc);

    // Calculate position within the observation window (agent is at the center)
    int obs_r = r - static_cast<int>(observer_row) + static_cast<int>(obs_height_radius);
    int obs_c = c - static_cast<int>(observer_col) + static_cast<int>(obs_width_radius);
    uint8_t location = PackedCoordinate::pack(static_cast<uint8_t>(obs_r), static_cast<uint8_t>(obs_c));

    size_t buffer_capacity = static_cast<size_t>(observation_view.shape(1));

    // Prepare observation buffer for this location
    ObservationToken* obs_ptr =
        reinterpret_cast<ObservationToken*>(observation_view.mutable_data(agent_idx, tokens_written, 0));

    _emit_tile_observability_tokens(
        agent_idx, object_loc, location, obs_ptr, tokens_written, attempted_tokens_written, buffer_capacity);

    if (!obj) {
      // Empty space: AOE token(s) (if any) are the only emissions for this location.
      tokens_written = std::min(attempted_tokens_written, buffer_capacity);
      continue;
    }

    // Track cell staleness for exploration (cell.visited stat)
    if (obj->visited < current_step) {
      unsigned int staleness = current_step - obj->visited;
      obj->visited = current_step;
      _agents[agent_idx]->stats.add("cell.visited", static_cast<float>(staleness));
    }

    // Encode location and add tokens
    ObservationTokens obs_tokens(obs_ptr, buffer_capacity - static_cast<size_t>(tokens_written));
    attempted_tokens_written += _obs_encoder->encode_tokens(obj, obs_tokens, location);
    tokens_written = std::min(attempted_tokens_written, buffer_capacity);
  }

  _stats->add("tokens_written", tokens_written);
  _stats->add("tokens_dropped", attempted_tokens_written - tokens_written);
  _stats->add("tokens_free_space", static_cast<size_t>(observation_view.shape(1)) - tokens_written);
}

// Optimized path: pre-computed offsets, buffer reuse, direct encoding
void MettaGrid::_compute_observation_optimized(GridCoord observer_row,
                                               GridCoord observer_col,
                                               ObservationCoord observable_width,
                                               ObservationCoord observable_height,
                                               size_t agent_idx,
                                               ActionType action) {
  // Calculate observation boundaries
  ObservationCoord obs_width_radius = observable_width >> 1;
  ObservationCoord obs_height_radius = observable_height >> 1;

  int r_start = std::max(static_cast<int>(observer_row) - static_cast<int>(obs_height_radius), 0);
  int c_start = std::max(static_cast<int>(observer_col) - static_cast<int>(obs_width_radius), 0);

  int r_end = std::min(static_cast<int>(observer_row) + static_cast<int>(obs_height_radius) + 1,
                       static_cast<int>(_grid->height));
  int c_end =
      std::min(static_cast<int>(observer_col) + static_cast<int>(obs_width_radius) + 1, static_cast<int>(_grid->width));

  // Fill in visible objects. Observations should have been cleared in _step, so
  // we don't need to do that here.
  size_t attempted_tokens_written = 0;
  size_t tokens_written = 0;
  auto observation_view = _observations.mutable_unchecked<3>();
  auto rewards_view = _rewards.unchecked<1>();

  // Global tokens
  ObservationToken* agent_obs_ptr = reinterpret_cast<ObservationToken*>(observation_view.mutable_data(agent_idx, 0, 0));
  ObservationTokens agent_obs_tokens(
      agent_obs_ptr, static_cast<size_t>(observation_view.shape(1)) - static_cast<size_t>(tokens_written));

  // Build global tokens based on configuration (reusing pre-allocated buffer)
  auto& global_tokens = _global_tokens_buffer;
  global_tokens.clear();

  if (_global_obs_config.episode_completion_pct) {
    ObservationType episode_completion_pct = 0;
    if (max_steps > 0) {
      if (current_step >= max_steps) {
        episode_completion_pct = std::numeric_limits<ObservationType>::max();
      } else {
        episode_completion_pct = static_cast<ObservationType>(
            (static_cast<uint32_t>(std::numeric_limits<ObservationType>::max()) + 1) * current_step / max_steps);
      }
    }
    global_tokens.push_back({ObservationFeature::EpisodeCompletionPct, episode_completion_pct});
  }

  if (_global_obs_config.last_action) {
    global_tokens.push_back({ObservationFeature::LastAction, static_cast<ObservationType>(action)});
  }

  if (ObservationFeature::LastActionMove != 0) {
    bool moved = !(_agents[agent_idx]->location == _prev_agent_locations[agent_idx]);
    global_tokens.push_back({ObservationFeature::LastActionMove, static_cast<ObservationType>(moved ? 1 : 0)});
  }

  if (_global_obs_config.last_reward) {
    RewardType reward = rewards_view(agent_idx);
    ObservationType reward_int = static_cast<ObservationType>(std::round(reward * 100.0f));
    global_tokens.push_back({ObservationFeature::LastReward, reward_int});
  }

  if (_global_obs_config.goal_obs) {
    global_tokens.insert(global_tokens.end(), _agent_goal_obs_tokens[agent_idx].begin(), _agent_goal_obs_tokens[agent_idx].end());
  }

  if (_global_obs_config.local_position) {
    auto& agent = *_agents[agent_idx];
    int dc = static_cast<int>(agent.location.c) - static_cast<int>(agent.spawn_location.c);
    int dr = static_cast<int>(agent.spawn_location.r) - static_cast<int>(agent.location.r);
    if (dc > 0) {
      global_tokens.push_back({ObservationFeature::LpEast, static_cast<ObservationType>(std::min(dc, 255))});
    } else if (dc < 0) {
      global_tokens.push_back({ObservationFeature::LpWest, static_cast<ObservationType>(std::min(-dc, 255))});
    }
    if (dr > 0) {
      global_tokens.push_back({ObservationFeature::LpNorth, static_cast<ObservationType>(std::min(dr, 255))});
    } else if (dr < 0) {
      global_tokens.push_back({ObservationFeature::LpSouth, static_cast<ObservationType>(std::min(-dr, 255))});
    }
  }

  // Global tokens use a dedicated location marker (0xFE) distinct from spatial coordinates.
  uint8_t global_location = PackedCoordinate::GLOBAL_LOCATION;

  attempted_tokens_written +=
      _obs_encoder->append_tokens_if_room_available(agent_obs_tokens, global_tokens, global_location);
  tokens_written = std::min(attempted_tokens_written, static_cast<size_t>(observation_view.shape(1)));

  // Emit obs tokens - resolve each GameValueConfig inline
  attempted_tokens_written += _emit_obs_value_tokens(agent_idx, tokens_written, global_location);
  tokens_written = std::min(attempted_tokens_written, static_cast<size_t>(observation_view.shape(1)));

  // Process locations in increasing manhattan distance order (using pre-computed offsets)
  for (const auto& [r_offset, c_offset] : _observation_offsets) {
    int r = static_cast<int>(observer_row) + r_offset;
    int c = static_cast<int>(observer_col) + c_offset;

    // Skip if outside map bounds
    if (r < r_start || r >= r_end || c < c_start || c >= c_end) {
      continue;
    }

    // Process a single grid location
    GridLocation object_loc(static_cast<GridCoord>(r), static_cast<GridCoord>(c));
    auto obj = _grid->object_at(object_loc);

    // Calculate position within the observation window (agent is at the center)
    int obs_r = r - static_cast<int>(observer_row) + static_cast<int>(obs_height_radius);
    int obs_c = c - static_cast<int>(observer_col) + static_cast<int>(obs_width_radius);
    uint8_t location = PackedCoordinate::pack(static_cast<uint8_t>(obs_r), static_cast<uint8_t>(obs_c));

    // Once buffer is full, we still compute features to track exact tokens_dropped.
    // Alternative: count objects only (cheaper, but tokens_dropped becomes objects_dropped).
    size_t buffer_capacity = static_cast<size_t>(observation_view.shape(1));
    ObservationToken* obs_ptr =
        reinterpret_cast<ObservationToken*>(observation_view.mutable_data(agent_idx, tokens_written, 0));

    _emit_tile_observability_tokens(
        agent_idx, object_loc, location, obs_ptr, tokens_written, attempted_tokens_written, buffer_capacity);

    if (!obj) {
      tokens_written = std::min(attempted_tokens_written, buffer_capacity);
      continue;
    }

    // Track cell staleness for exploration (cell.visited stat)
    if (obj->visited < current_step) {
      unsigned int staleness = current_step - obj->visited;
      obj->visited = current_step;
      _agents[agent_idx]->stats.add("cell.visited", static_cast<float>(staleness));
    }

    if (tokens_written >= buffer_capacity) {
      attempted_tokens_written += obj->write_obs_features(_obs_features_scratch.data(), _obs_features_scratch.size());
      continue;
    }

    // Prepare observation buffer for this object
    ObservationTokens obs_tokens(obs_ptr, buffer_capacity - tokens_written);

    // Encode location and add tokens (using allocation-free path with scratch buffer)
    attempted_tokens_written += _obs_encoder->encode_tokens_direct(
        obj, obs_tokens, location, _obs_features_scratch.data(), _obs_features_scratch.size());
    tokens_written = std::min(attempted_tokens_written, buffer_capacity);
  }

  *_stats->get_ptr(_stat_tokens_written) += tokens_written;
  *_stats->get_ptr(_stat_tokens_dropped) += (attempted_tokens_written - tokens_written);
  *_stats->get_ptr(_stat_tokens_free_space) += (static_cast<size_t>(observation_view.shape(1)) - tokens_written);
}

void MettaGrid::_compute_observations(const std::vector<ActionType>& executed_actions) {
  for (size_t idx = 0; idx < _agents.size(); idx++) {
    auto& agent = _agents[idx];
    ActionType action_idx = executed_actions[idx];
    _compute_observation(agent->location.r, agent->location.c, obs_width, obs_height, idx, action_idx);
  }
}

void MettaGrid::_handle_invalid_action(size_t agent_idx, const std::string& stat, ActionType type) {
  auto& agent = _agents[agent_idx];
  agent->stats.incr(stat);
  agent->stats.incr(stat + "." + std::to_string(type));
  _action_success[agent_idx] = false;
}

void MettaGrid::_step() {
  std::chrono::steady_clock::time_point step_start, phase_start, phase_end;
  if (_profiling_enabled) {
    step_start = std::chrono::steady_clock::now();
  }
  auto actions_view = _actions.unchecked<1>();

  for (size_t i = 0; i < _agents.size(); ++i) {
    _prev_agent_locations[i] = _agents[i]->location;
  }

  // Reset rewards and observations
  if (_profiling_enabled) phase_start = std::chrono::steady_clock::now();
  auto rewards_view = _rewards.mutable_unchecked<1>();

  std::fill(
      static_cast<float*>(_rewards.request().ptr), static_cast<float*>(_rewards.request().ptr) + _rewards.size(), 0);

  auto obs_ptr = static_cast<ObservationType*>(_observations.request().ptr);
  auto obs_size = _observations.size();
  std::fill(obs_ptr, obs_ptr + obs_size, EmptyTokenByte);

  std::fill(_action_success.begin(), _action_success.end(), false);
  if (_profiling_enabled) {
    phase_end = std::chrono::steady_clock::now();
    _step_timing.reset_ns = std::chrono::duration<double, std::nano>(phase_end - phase_start).count();
  }

  // Increment timestep and process events
  if (_profiling_enabled) phase_start = std::chrono::steady_clock::now();
  current_step++;

  // Process events at current timestep
  if (_event_scheduler) {
    mettagrid::HandlerContext event_ctx;
    event_ctx.tag_index = &_tag_index;
    event_ctx.grid = _grid.get();
    event_ctx.game_stats = _stats.get();
    event_ctx.collectives = &_collectives;
    event_ctx.query_system = _query_system.get();
    _event_scheduler->process_timestep(current_step, event_ctx);
  }
  if (_profiling_enabled) {
    phase_end = std::chrono::steady_clock::now();
    _step_timing.events_ns = std::chrono::duration<double, std::nano>(phase_end - phase_start).count();
  }

  // Create and shuffle agent indices for randomized action order
  if (_profiling_enabled) phase_start = std::chrono::steady_clock::now();
  std::vector<size_t> agent_indices(_agents.size());
  std::iota(agent_indices.begin(), agent_indices.end(), 0);
  std::shuffle(agent_indices.begin(), agent_indices.end(), _rng);

  std::vector<ActionType> executed_actions(_agents.size());
  // Fill with noop. Replace this with the actual action if it's successful.
  std::fill(executed_actions.begin(), executed_actions.end(), ActionType(0));
  // Process actions by priority levels (highest to lowest)
  for (unsigned char offset = 0; offset <= _max_action_priority; offset++) {
    unsigned char current_priority = _max_action_priority - offset;

    for (const auto& agent_idx : agent_indices) {
      ActionType action_idx = actions_view(agent_idx);

      if (action_idx < 0 || static_cast<size_t>(action_idx) >= _action_handlers.size()) {
        _handle_invalid_action(agent_idx, "action.invalid_index", action_idx);
        continue;
      }

      Action& action = _action_handlers[static_cast<size_t>(action_idx)];
      if (action.handler()->priority != current_priority) {
        continue;
      }

      auto* agent = _agents[agent_idx];
      bool success = action.handle(*agent);
      _action_success[agent_idx] = success;
      if (success) {
        executed_actions[agent_idx] = action_idx;
      }
    }
  }
  if (_profiling_enabled) {
    phase_end = std::chrono::steady_clock::now();
    _step_timing.actions_ns = std::chrono::duration<double, std::nano>(phase_end - phase_start).count();
  }

  // Apply per-agent on_tick handlers
  if (_profiling_enabled) phase_start = std::chrono::steady_clock::now();
  for (auto* agent : _agents) {
    mettagrid::HandlerContext ctx;
    ctx.actor = agent;
    ctx.target = agent;
    ctx.game_stats = _stats.get();
    ctx.tag_index = &_tag_index;
    ctx.grid = _grid.get();
    ctx.collectives = &_collectives;
    ctx.query_system = _query_system.get();
    agent->apply_on_tick(ctx);
  }
  if (_profiling_enabled) {
    phase_end = std::chrono::steady_clock::now();
    _step_timing.on_tick_ns = std::chrono::duration<double, std::nano>(phase_end - phase_start).count();
  }

  // Apply fixed AOE effects to all agents at their current location
  if (_profiling_enabled) phase_start = std::chrono::steady_clock::now();
  for (auto* agent : _agents) {
    _aoe_tracker->apply_fixed(*agent);
  }

  // Apply mobile AOE effects (sources checked against all agents)
  _aoe_tracker->apply_mobile(_agents);
  if (_profiling_enabled) {
    phase_end = std::chrono::steady_clock::now();
    _step_timing.aoe_ns = std::chrono::duration<double, std::nano>(phase_end - phase_start).count();
  }

  // Update held stats for all collectives (tracks how long objects are aligned)
  if (_profiling_enabled) phase_start = std::chrono::steady_clock::now();
  for (auto& collective : _collectives) {
    collective->update_held_stats();
  }
  if (_profiling_enabled) {
    phase_end = std::chrono::steady_clock::now();
    _step_timing.collectives_ns = std::chrono::duration<double, std::nano>(phase_end - phase_start).count();
  }

  // Compute observations for next step
  if (_profiling_enabled) phase_start = std::chrono::steady_clock::now();
  _compute_observations(executed_actions);
  if (_profiling_enabled) {
    phase_end = std::chrono::steady_clock::now();
    _step_timing.observations_ns = std::chrono::duration<double, std::nano>(phase_end - phase_start).count();
  }

  // Compute rewards for all agents
  if (_profiling_enabled) phase_start = std::chrono::steady_clock::now();
  for (auto& agent : _agents) {
    agent->reward_helper.compute_entries();
  }

  // Update episode rewards
  auto episode_rewards_view = _episode_rewards.mutable_unchecked<1>();
  for (py::ssize_t i = 0; i < rewards_view.shape(0); i++) {
    episode_rewards_view(i) += rewards_view(i);
  }
  if (_profiling_enabled) {
    phase_end = std::chrono::steady_clock::now();
    _step_timing.rewards_ns = std::chrono::duration<double, std::nano>(phase_end - phase_start).count();
  }

  // Check for truncation
  if (_profiling_enabled) phase_start = std::chrono::steady_clock::now();
  if (max_steps > 0 && current_step >= max_steps) {
    if (episode_truncates) {
      std::fill(static_cast<bool*>(_truncations.request().ptr),
                static_cast<bool*>(_truncations.request().ptr) + _truncations.size(),
                1);
    } else {
      std::fill(static_cast<bool*>(_terminals.request().ptr),
                static_cast<bool*>(_terminals.request().ptr) + _terminals.size(),
                1);
    }
  }
  if (_profiling_enabled) {
    phase_end = std::chrono::steady_clock::now();
    _step_timing.truncation_ns = std::chrono::duration<double, std::nano>(phase_end - phase_start).count();
    _step_timing.total_ns = std::chrono::duration<double, std::nano>(phase_end - step_start).count();
  }
}

void MettaGrid::validate_buffers() {
  // We should validate once buffers and agents are set.
  // data types and contiguity are handled by pybind11. We still need to check
  // shape.
  auto num_agents = _agents.size();
  auto observation_info = _observations.request();
  auto observation_shape = observation_info.shape;
  if (observation_info.ndim != 3) {
    std::stringstream ss;
    ss << "observations has " << observation_info.ndim << " dimensions but expected 3";
    throw std::runtime_error(ss.str());
  }
  if (observation_shape[0] != static_cast<ssize_t>(num_agents) || observation_shape[2] != 3) {
    std::stringstream ss;
    ss << "observations has shape [" << observation_shape[0] << ", " << observation_shape[1] << ", "
       << observation_shape[2] << "] but expected [" << num_agents << ", [something], 3]";
    throw std::runtime_error(ss.str());
  }
  {
    auto terminals_info = _terminals.request();
    auto terminals_shape = terminals_info.shape;
    if (terminals_info.ndim != 1 || terminals_shape[0] != static_cast<ssize_t>(num_agents)) {
      throw std::runtime_error("terminals has the wrong shape");
    }
  }
  {
    auto truncations_info = _truncations.request();
    auto truncations_shape = truncations_info.shape;
    if (truncations_info.ndim != 1 || truncations_shape[0] != static_cast<ssize_t>(num_agents)) {
      throw std::runtime_error("truncations has the wrong shape");
    }
  }
  {
    auto rewards_info = _rewards.request();
    auto rewards_shape = rewards_info.shape;
    if (rewards_info.ndim != 1 || rewards_shape[0] != static_cast<ssize_t>(num_agents)) {
      throw std::runtime_error("rewards has the wrong shape");
    }
  }
}

void MettaGrid::set_buffers(const py::array_t<uint8_t, py::array::c_style>& observations,
                            const py::array_t<bool, py::array::c_style>& terminals,
                            const py::array_t<bool, py::array::c_style>& truncations,
                            const py::array_t<float, py::array::c_style>& rewards,
                            const py::array_t<ActionType, py::array::c_style>& actions) {
  // These are initialized in reset()
  _observations = observations;
  _terminals = terminals;
  _truncations = truncations;
  _rewards = rewards;
  _actions = actions;
  for (size_t i = 0; i < _agents.size(); i++) {
    _agents[i]->init(&_rewards.mutable_unchecked<1>()(i));
  }

  validate_buffers();
  _init_buffers(_agents.size());
}

void MettaGrid::step() {
  auto info = _actions.request();

  // Validate that actions array has correct shape
  if (info.ndim != 1) {
    throw std::runtime_error("actions must be 1D array");
  }
  if (info.shape[0] != static_cast<ssize_t>(_agents.size())) {
    throw std::runtime_error("actions has the wrong shape");
  }

  _step();
}

size_t MettaGrid::_emit_obs_value_tokens(size_t agent_idx, size_t tokens_written, ObservationType global_location) {
  auto observation_view = _observations.mutable_unchecked<3>();
  auto* agent = _agents[agent_idx];

  // Build a HandlerContext so we can use resolve_game_value
  mettagrid::HandlerContext ctx;
  ctx.actor = agent;
  ctx.target = agent;
  ctx.game_stats = _stats.get();
  ctx.tag_index = &_tag_index;
  ctx.collectives = &_collectives;
  ctx.query_system = _query_system.get();

  size_t total_written = 0;

  for (const auto& obs_cfg : _game_config.global_obs.obs) {
    if (tokens_written + total_written >= static_cast<size_t>(observation_view.shape(1))) {
      break;
    }

    const auto& gv = obs_cfg.value;
    float raw_value = ctx.resolve_game_value(gv, mettagrid::EntityRef::actor);

    auto tokens = _token_encoder->encode(obs_cfg.feature_id, static_cast<uint32_t>(raw_value));
    ObservationToken* ptr = reinterpret_cast<ObservationToken*>(
        observation_view.mutable_data(agent_idx, tokens_written + total_written, 0));
    ObservationTokens obs_tokens(ptr, static_cast<size_t>(observation_view.shape(1)) - tokens_written - total_written);
    total_written += _obs_encoder->append_tokens_if_room_available(obs_tokens, tokens, global_location);
  }

  return total_written;
}
