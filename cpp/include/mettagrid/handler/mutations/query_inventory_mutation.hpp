#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_QUERY_INVENTORY_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_QUERY_INVENTORY_MUTATION_HPP_

#include <cassert>
#include <unordered_map>

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
          InventoryDelta actual = 0;
          if (delta > 0) {
            // Transfer from source to query result
            actual = HasInventory::transfer_resources(source->inventory, obj->inventory, resource_id, delta, false);
          } else if (delta < 0) {
            // Transfer from query result to source
            actual = HasInventory::transfer_resources(obj->inventory, source->inventory, resource_id, -delta, false);
          }
          _log_transfer_stat(ctx, resource_id, actual);
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
  void _log_transfer_stat(HandlerContext& ctx, InventoryItem resource_id, InventoryDelta actual) {
    if (actual == 0 || _stat_name_by_resource.empty()) return;
    auto it = _stat_name_by_resource.find(resource_id);
    if (it != _stat_name_by_resource.end()) {
      ctx.game_stats->add(it->second, static_cast<float>(actual));
    }
  }

  static std::unordered_map<InventoryItem, std::string> _build_stat_map(
      const std::vector<std::pair<InventoryItem, std::string>>& names) {
    std::unordered_map<InventoryItem, std::string> m;
    m.reserve(names.size());
    for (const auto& [id, name] : names) {
      m[id] = name;
    }
    return m;
  }

  QueryInventoryMutationConfig _config;
  std::unordered_map<InventoryItem, std::string> _stat_name_by_resource = _build_stat_map(_config.transfer_stat_names);
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_QUERY_INVENTORY_MUTATION_HPP_
