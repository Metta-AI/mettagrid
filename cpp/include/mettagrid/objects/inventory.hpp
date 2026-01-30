#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_INVENTORY_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_INVENTORY_HPP_

#include <algorithm>
#include <limits>
#include <memory>
#include <unordered_map>
#include <vector>

#include "core/types.hpp"
#include "objects/constants.hpp"
#include "objects/inventory_config.hpp"

class HasInventory;

struct SharedInventoryLimit {
  InventoryQuantity min_limit;
  InventoryQuantity max_limit;
  // Modifiers: item_id -> bonus_per_item
  std::unordered_map<InventoryItem, InventoryQuantity> modifiers;
  // How much do we have of whatever-this-limit-applies-to
  InventoryQuantity amount;

  // Get the effective limit: min(max_limit, max(min_limit, sum(modifier_bonus * quantity_held)))
  // This ensures min_limit acts as a floor and max_limit acts as a ceiling.
  InventoryQuantity effective_limit(const std::unordered_map<InventoryItem, InventoryQuantity>& inventory) const {
    int modifier_sum = 0;
    for (const auto& [item, bonus] : modifiers) {
      auto it = inventory.find(item);
      if (it != inventory.end()) {
        modifier_sum += static_cast<int>(it->second) * static_cast<int>(bonus);
      }
    }
    // Apply formula: min(max_limit, max(min_limit, modifier_sum))
    // This avoids UB from std::clamp when min_limit > max_limit; max_limit wins in that case.
    int effective = std::min(static_cast<int>(max_limit), std::max(static_cast<int>(min_limit), modifier_sum));
    // Clamp to valid range (0 to max InventoryQuantity which is uint16_t)
    effective = std::clamp(effective, 0, 65535);
    return static_cast<InventoryQuantity>(effective);
  }
};

class Inventory {
private:
  std::unordered_map<InventoryItem, InventoryQuantity> _inventory;
  std::unordered_map<InventoryItem, SharedInventoryLimit*> _limits;
  // The HasInventory that owns this inventory. If we want multiple things to react to changes,
  // we can make this a vector.
  HasInventory* _owner;

public:
  // Constructor and Destructor
  explicit Inventory(const InventoryConfig& cfg, HasInventory* owner = nullptr);
  ~Inventory();

  // Update the inventory for a specific item
  // If ignore_limits is true, the update will bypass limit checks (used for initial inventory)
  InventoryDelta update(InventoryItem item, InventoryDelta attempted_delta, bool ignore_limits = false);

  // Get the amount of a specific item
  InventoryQuantity amount(InventoryItem item) const;

  // Get the free space for a specific item
  InventoryQuantity free_space(InventoryItem item) const;

  // Get all inventory items
  std::unordered_map<InventoryItem, InventoryQuantity> get() const;

  // Enforce all limits - drop excess items when limits decrease (e.g., after losing gear modifiers)
  void enforce_all_limits();

  // Check if the inventory is completely empty (all items have 0 quantity)
  bool is_empty() const;

  // Check if an item is a modifier for any limit
  bool is_modifier(InventoryItem item) const;
};

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_OBJECTS_INVENTORY_HPP_
