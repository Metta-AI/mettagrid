#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_RAYCAST_SPAWN_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_RAYCAST_SPAWN_MUTATION_HPP_

#include <string>

#include "core/mutation_config.hpp"
#include "handler/mutations/mutation.hpp"

namespace mettagrid {

/**
 * RaycastSpawnMutation: Walk rays from target and spawn objects
 * at empty cells along each ray. Stops at blockers.
 */
class RaycastSpawnMutation : public Mutation {
public:
  explicit RaycastSpawnMutation(const RaycastSpawnMutationConfig& config) : _config(config) {}

  void apply(HandlerContext& ctx) override;

private:
  RaycastSpawnMutationConfig _config;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_RAYCAST_SPAWN_MUTATION_HPP_
