#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_ATTACK_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_ATTACK_MUTATION_HPP_

#include <algorithm>

#include "handler/handler_config.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation.hpp"

namespace mettagrid {

/**
 * AttackMutation: Combat with weapon/armor/health
 */
class AttackMutation : public Mutation {
public:
  explicit AttackMutation(const AttackMutationConfig& config) : _config(config) {}

  void apply(HandlerContext& ctx) override {
    if (ctx.actor == nullptr || ctx.target == nullptr) {
      return;
    }

    // Get weapon power from actor
    InventoryQuantity weapon = ctx.actor->inventory.amount(_config.weapon_resource);

    // Get armor from target
    InventoryQuantity armor = ctx.target->inventory.amount(_config.armor_resource);

    // Calculate damage using integer math (percentage-based multiplier)
    InventoryDelta raw_damage = (static_cast<InventoryDelta>(weapon) * _config.damage_multiplier_pct) / 100;
    InventoryDelta damage = std::max(static_cast<InventoryDelta>(0), raw_damage - static_cast<InventoryDelta>(armor));

    // Apply damage to target's health
    if (damage > 0) {
      ctx.target->inventory.update(_config.health_resource, -damage);
    }
  }

private:
  AttackMutationConfig _config;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_ATTACK_MUTATION_HPP_
