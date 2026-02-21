#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_RESOURCE_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_RESOURCE_MUTATION_HPP_

#include <cassert>

#include "core/grid.hpp"
#include "core/grid_object.hpp"
#include "core/tag_index.hpp"
#include "handler/handler_config.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation.hpp"
#include "objects/agent.hpp"
#include "objects/has_inventory.hpp"

namespace mettagrid {

/**
 * ResourceDeltaMutation: Add/remove resources from an entity
 */
class ResourceDeltaMutation : public Mutation {
public:
  explicit ResourceDeltaMutation(const ResourceDeltaMutationConfig& config) : _config(config) {}

  void apply(HandlerContext& ctx) override {
    // In some hot paths (notably fixed AOEs), we want to apply a single net delta per resource to
    // avoid intermediate clamp artifacts (e.g. heal clamped to max, then damage applied).
    if (ctx.deferred_target_resource_deltas != nullptr && _config.entity == EntityRef::target &&
        ctx.target != nullptr) {
      // Avoid deferring "modifier" items that affect limits, since deferral would collapse important
      // ordering semantics for subsequent clamping.
      if (!ctx.target->inventory.is_modifier(_config.resource_id)) {
        if (ctx.deferred_target_resource_order != nullptr && ctx.deferred_target_resource_seen != nullptr) {
          if (ctx.deferred_target_resource_seen->insert(_config.resource_id).second) {
            ctx.deferred_target_resource_order->push_back(_config.resource_id);
          }
        }
        (*ctx.deferred_target_resource_deltas)[_config.resource_id] += _config.delta;
        return;
      }
    }

    HasInventory* entity = ctx.resolve_inventory(_config.entity);
    assert(entity && "ResourceDeltaMutation entity must resolve");

    entity->inventory.update(_config.resource_id, _config.delta);
  }

private:
  ResourceDeltaMutationConfig _config;
};

/**
 * ResourceTransferMutation: Move resources between entities
 */
class ResourceTransferMutation : public Mutation {
public:
  explicit ResourceTransferMutation(const ResourceTransferMutationConfig& config) : _config(config) {}

  void apply(HandlerContext& ctx) override {
    HasInventory* source = ctx.resolve_inventory(_config.source);
    HasInventory* dest = ctx.resolve_inventory(_config.destination);
    assert(source && "ResourceTransferMutation source must resolve");
    assert(dest && "ResourceTransferMutation destination must resolve");

    InventoryDelta amount = _config.amount;
    if (amount < 0) {
      // Transfer all available
      amount = static_cast<InventoryDelta>(source->inventory.amount(_config.resource_id));
    }

    InventoryDelta transferred = HasInventory::transfer_resources(source->inventory,
                                                                  dest->inventory,
                                                                  _config.resource_id,
                                                                  amount,
                                                                  false  // Don't destroy untransferred resources
    );

    // Track per-agent deposit stats
    if (transferred > 0) {
      Agent* source_agent = dynamic_cast<Agent*>(source);
      if (source_agent) {
        source_agent->stats.add(source_agent->stats.resource_name(_config.resource_id) + ".deposited", transferred);
      }
    }

    // Remove source from grid and tag index when its inventory is depleted
    if (_config.remove_source_when_empty && source->inventory.is_empty()) {
      GridObject* grid_obj = dynamic_cast<GridObject*>(source);
      if (grid_obj != nullptr) {
        ctx.grid->remove_from_grid(*grid_obj);
        ctx.tag_index->unregister_object(grid_obj);
      }
    }
  }

private:
  ResourceTransferMutationConfig _config;
};

/**
 * ClearInventoryMutation: Clear resources from entity
 */
class ClearInventoryMutation : public Mutation {
public:
  explicit ClearInventoryMutation(const ClearInventoryMutationConfig& config) : _config(config) {}

  void apply(HandlerContext& ctx) override {
    HasInventory* entity = ctx.resolve_inventory(_config.entity);
    assert(entity && "ClearInventoryMutation entity must resolve");

    if (_config.resource_ids.empty()) {
      // Clear all resources
      auto items = entity->inventory.get();
      for (const auto& [item, amount] : items) {
        entity->inventory.update(item, -static_cast<InventoryDelta>(amount));
      }
    } else {
      // Clear specific resources in the list
      for (const auto& resource_id : _config.resource_ids) {
        InventoryQuantity amount = entity->inventory.amount(resource_id);
        entity->inventory.update(resource_id, -static_cast<InventoryDelta>(amount));
      }
    }
  }

private:
  ClearInventoryMutationConfig _config;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_RESOURCE_MUTATION_HPP_
