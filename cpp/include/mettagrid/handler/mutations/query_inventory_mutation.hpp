#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_QUERY_INVENTORY_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_QUERY_INVENTORY_MUTATION_HPP_

#include <cassert>

#include "core/grid_object.hpp"
#include "core/query_config.hpp"
#include "handler/handler_config.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation.hpp"
#include "objects/has_inventory.hpp"

namespace mettagrid {

/**
 * QueryInventoryMutation: Apply inventory deltas to objects found by query.
 *
 * Evaluates the query via QuerySystem, then applies deltas to each result's inventory.
 * If has_source is true, transfers resources between source entity and query results.
 */
class QueryInventoryMutation : public Mutation {
public:
  explicit QueryInventoryMutation(const QueryInventoryMutationConfig& config) : _config(config) {}

  void apply(HandlerContext& ctx) override {
    auto results = _config.query->evaluate(ctx);

    if (_config.has_source) {
      auto* source = ctx.resolve_inventory(_config.source);
      assert(source && "QueryInventoryMutation source must resolve");
      for (GridObject* obj : results) {
        for (const auto& [resource_id, delta] : _config.deltas) {
          if (delta > 0) {
            // Transfer from source to query result
            HasInventory::transfer_resources(source->inventory, obj->inventory, resource_id, delta, false);
          } else if (delta < 0) {
            // Transfer from query result to source
            HasInventory::transfer_resources(obj->inventory, source->inventory, resource_id, -delta, false);
          }
        }
      }
    } else {
      for (GridObject* obj : results) {
        for (const auto& [resource_id, delta] : _config.deltas) {
          obj->inventory.update(resource_id, delta);
        }
      }
    }
  }

private:
  QueryInventoryMutationConfig _config;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_QUERY_INVENTORY_MUTATION_HPP_
