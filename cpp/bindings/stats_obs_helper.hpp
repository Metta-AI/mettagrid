#ifndef PACKAGES_METTAGRID_CPP_BINDINGS_STATS_OBS_HELPER_HPP_
#define PACKAGES_METTAGRID_CPP_BINDINGS_STATS_OBS_HELPER_HPP_

#include <pybind11/numpy.h>

#include <memory>
#include <vector>

#include "config/mettagrid_config.hpp"
#include "core/grid_object.hpp"
#include "objects/agent.hpp"
#include "objects/collective.hpp"
#include "systems/encoding_utils.hpp"
#include "systems/observation_encoder.hpp"
#include "systems/stats_tracker.hpp"

namespace py = pybind11;

// Encapsulates stats observation initialization, precomputation, and emission.
class StatsObsHelper {
public:
  StatsObsHelper(const GlobalObsConfig& global_obs_config, unsigned int token_value_base)
      : _global_obs_config(global_obs_config), _encoder(token_value_base) {}

  // Register observations on appropriate trackers by source
  void init(std::vector<Agent*>& agents,
            StatsTracker* global_stats,
            std::vector<std::unique_ptr<Collective>>& collectives) {
    if (_global_obs_config.stats_obs.empty()) return;

    for (const auto& cfg : _global_obs_config.stats_obs) {
      switch (cfg.source) {
        case StatsSource::Own:
          for (auto& agent : agents) {
            agent->stats.register_observation(cfg.name, cfg.feature_id, cfg.delta);
          }
          break;
        case StatsSource::Global:
          global_stats->register_observation(cfg.name, cfg.feature_id, cfg.delta);
          break;
        case StatsSource::Collective:
          for (auto& collective : collectives) {
            collective->stats.register_observation(cfg.name, cfg.feature_id, cfg.delta);
          }
          break;
      }
    }
  }

  // Precompute observation values once per timestep (before per-agent emission)
  void precompute(std::vector<Agent*>& agents,
                  StatsTracker* global_stats,
                  std::vector<std::unique_ptr<Collective>>& collectives) {
    global_stats->precompute_observation_values();
    for (auto& collective : collectives) {
      collective->stats.precompute_observation_values();
    }
    for (auto& agent : agents) {
      agent->stats.precompute_observation_values();
    }
  }

  // Emit stat tokens for a given tracker into the observation buffer
  size_t emit(StatsTracker& tracker,
              ObservationEncoder& obs_encoder,
              py::array_t<uint8_t>& observations,
              size_t agent_idx,
              size_t tokens_written,
              ObservationType global_location) {
    auto values = tracker.observation_values();
    auto observation_view = observations.mutable_unchecked<3>();

    size_t total_written = 0;
    for (const auto& val : values) {
      // Check bounds before accessing observation buffer
      if (tokens_written + total_written >= static_cast<size_t>(observation_view.shape(1))) {
        break;  // No more room, stop emitting
      }
      auto tokens = _encoder.encode(val.feature_id, val.value);
      ObservationToken* stat_obs_ptr = reinterpret_cast<ObservationToken*>(
          observation_view.mutable_data(agent_idx, tokens_written + total_written, 0));
      ObservationTokens stat_obs_tokens(
          stat_obs_ptr, static_cast<size_t>(observation_view.shape(1)) - tokens_written - total_written);
      total_written += obs_encoder.append_tokens_if_room_available(stat_obs_tokens, tokens, global_location);
    }
    return total_written;
  }

private:
  const GlobalObsConfig& _global_obs_config;
  ObservationTokenEncoder _encoder;
};

#endif  // PACKAGES_METTAGRID_CPP_BINDINGS_STATS_OBS_HELPER_HPP_
