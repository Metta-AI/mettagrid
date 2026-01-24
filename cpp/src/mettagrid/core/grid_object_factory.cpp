#include "core/grid_object_factory.hpp"

#include <memory>
#include <stdexcept>
#include <typeinfo>
#include <vector>

#include "core/grid.hpp"
#include "handler/handler.hpp"
#include "objects/agent.hpp"
#include "objects/agent_config.hpp"
#include "objects/assembler.hpp"
#include "objects/assembler_config.hpp"
#include "objects/chest.hpp"
#include "objects/chest_config.hpp"
#include "objects/wall.hpp"
#include "systems/observation_encoder.hpp"
#include "systems/stats_tracker.hpp"

namespace mettagrid {

// Set up handlers on a GridObject from its config
static void _set_up_handlers(GridObject* obj, const GridObjectConfig* config) {
  // on_use handlers
  std::vector<std::shared_ptr<Handler>> on_use_handlers;
  on_use_handlers.reserve(config->on_use_handlers.size());
  for (const auto& handler_config : config->on_use_handlers) {
    on_use_handlers.push_back(std::make_shared<Handler>(handler_config));
  }
  obj->set_on_use_handlers(std::move(on_use_handlers));

  // on_update handlers
  std::vector<std::shared_ptr<Handler>> on_update_handlers;
  on_update_handlers.reserve(config->on_update_handlers.size());
  for (const auto& handler_config : config->on_update_handlers) {
    on_update_handlers.push_back(std::make_shared<Handler>(handler_config));
  }
  obj->set_on_update_handlers(std::move(on_update_handlers));

  // AOE handlers
  std::vector<std::shared_ptr<Handler>> aoe_handlers;
  aoe_handlers.reserve(config->aoe_handlers.size());
  for (const auto& handler_config : config->aoe_handlers) {
    aoe_handlers.push_back(std::make_shared<Handler>(handler_config));
  }
  obj->set_aoe_handlers(std::move(aoe_handlers));
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
    auto* obj = new Agent(r, c, *agent_config, resource_names);
    obj->set_obs_encoder(obs_encoder);
    return obj;
  }

  if (const auto* assembler_config = dynamic_cast<const AssemblerConfig*>(config)) {
    auto* obj = new Assembler(r, c, *assembler_config, stats);
    obj->set_grid(grid);
    obj->set_current_timestep_ptr(current_timestep_ptr);
    obj->set_obs_encoder(obs_encoder);
    return obj;
  }

  if (const auto* chest_config = dynamic_cast<const ChestConfig*>(config)) {
    auto* obj = new Chest(r, c, *chest_config, stats);
    obj->set_grid(grid);
    obj->set_obs_encoder(obs_encoder);
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
                                      TagIndex* tag_index) {
  auto* obj = _create_object(r, c, config, stats, resource_names, grid, obs_encoder, current_timestep_ptr);
  _set_up_handlers(obj, config);
  return obj;
}

}  // namespace mettagrid
