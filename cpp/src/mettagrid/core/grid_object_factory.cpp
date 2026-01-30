#include "core/grid_object_factory.hpp"

#include <cassert>
#include <memory>
#include <stdexcept>
#include <typeinfo>
#include <vector>

#include "core/grid.hpp"
#include "handler/handler.hpp"
#include "objects/agent.hpp"
#include "objects/agent_config.hpp"
#include "objects/alignable.hpp"
#include "objects/chest.hpp"
#include "objects/chest_config.hpp"
#include "objects/collective.hpp"
#include "objects/wall.hpp"
#include "systems/observation_encoder.hpp"
#include "systems/stats_tracker.hpp"

namespace mettagrid {

// Set up handlers on a GridObject from its config
static void _set_up_handlers(GridObject* obj, const GridObjectConfig* config, TagIndex* tag_index) {
  // on_use handlers
  std::vector<std::shared_ptr<Handler>> on_use_handlers;
  on_use_handlers.reserve(config->on_use_handlers.size());
  for (const auto& handler_config : config->on_use_handlers) {
    on_use_handlers.push_back(std::make_shared<Handler>(handler_config, tag_index));
  }
  obj->set_on_use_handlers(std::move(on_use_handlers));

  // AOE configs - just copy them, AOETracker will instantiate filters/mutations
  obj->set_aoe_configs(config->aoe_configs);

  // on_tick handlers (agent-only)
  if (const auto* agent_config = dynamic_cast<const AgentConfig*>(config)) {
    if (!agent_config->on_tick.empty()) {
      auto* agent = dynamic_cast<Agent*>(obj);
      if (agent) {
        std::vector<std::shared_ptr<Handler>> on_tick;
        on_tick.reserve(agent_config->on_tick.size());
        for (const auto& handler_config : agent_config->on_tick) {
          on_tick.push_back(std::make_shared<Handler>(handler_config, tag_index));
        }
        agent->set_on_tick(std::move(on_tick));
      }
    }
  }
}

// Create a GridObject from config (without handlers)
static GridObject* _create_object(GridCoord r,
                                  GridCoord c,
                                  const GridObjectConfig* config,
                                  StatsTracker* stats,
                                  const std::vector<std::string>* resource_names,
                                  Grid* grid,
                                  const ObservationEncoder* obs_encoder,
                                  unsigned int* current_timestep_ptr) {
  // Try each config type in order
  // TODO: replace the dynamic casts with virtual dispatch

  if (const auto* wall_config = dynamic_cast<const WallConfig*>(config)) {
    return new Wall(r, c, *wall_config);
  }

  if (const auto* agent_config = dynamic_cast<const AgentConfig*>(config)) {
    return new Agent(r, c, *agent_config, resource_names);
  }

  if (const auto* chest_config = dynamic_cast<const ChestConfig*>(config)) {
    auto* obj = new Chest(r, c, *chest_config, stats);
    obj->set_grid(grid);
    return obj;
  }

  // Handle base GridObjectConfig as a static object (e.g., stations)
  if (typeid(*config) == typeid(GridObjectConfig)) {
    auto* obj = new GridObject(config->inventory_config);
    obj->init(config->type_id, config->type_name, GridLocation(r, c), config->tag_ids, config->initial_vibe);
    return obj;
  }

  // Unknown derived config type - likely a missing factory update
  throw std::runtime_error("Unknown GridObjectConfig subtype: " + config->type_name +
                           " (type_id=" + std::to_string(config->type_id) + ")");
}

GridObject* create_object_from_config(GridCoord r,
                                      GridCoord c,
                                      const GridObjectConfig* config,
                                      StatsTracker* stats,
                                      const std::vector<std::string>* resource_names,
                                      Grid* grid,
                                      const ObservationEncoder* obs_encoder,
                                      unsigned int* current_timestep_ptr,
                                      TagIndex* tag_index,
                                      const std::vector<Collective*>* collectives_by_id) {
  auto* obj = _create_object(r, c, config, stats, resource_names, grid, obs_encoder, current_timestep_ptr);
  obj->set_obs_encoder(obs_encoder);
  _set_up_handlers(obj, config, tag_index);

  // Set collective if specified in config (all GridObjects inherit from Alignable)
  assert(collectives_by_id != nullptr);
  if (config->collective_id >= 0 && static_cast<size_t>(config->collective_id) < collectives_by_id->size()) {
    obj->setCollective((*collectives_by_id)[config->collective_id]);
  }

  return obj;
}

}  // namespace mettagrid
