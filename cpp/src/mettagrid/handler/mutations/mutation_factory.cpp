#include "handler/mutations/mutation_factory.hpp"

#include <type_traits>

#include "handler/mutations/attack_mutation.hpp"
#include "handler/mutations/change_vibe_mutation.hpp"
#include "handler/mutations/game_value_mutation.hpp"
#include "handler/mutations/query_inventory_mutation.hpp"
#include "handler/mutations/raycast_spawn_mutation.hpp"
#include "handler/mutations/recompute_materialized_query_mutation.hpp"
#include "handler/mutations/relocate_mutation.hpp"
#include "handler/mutations/resource_mutation.hpp"
#include "handler/mutations/spawn_object_mutation.hpp"
#include "handler/mutations/stats_mutation.hpp"
#include "handler/mutations/swap_mutation.hpp"
#include "handler/mutations/tag_mutation.hpp"
#include "handler/mutations/use_target_mutation.hpp"

namespace mettagrid {

std::unique_ptr<Mutation> create_mutation(const MutationConfig& config) {
  return std::visit(
      [](auto&& cfg) -> std::unique_ptr<Mutation> {
        using T = std::decay_t<decltype(cfg)>;
        if constexpr (std::is_same_v<T, ResourceDeltaMutationConfig>) {
          return std::make_unique<ResourceDeltaMutation>(cfg);
        } else if constexpr (std::is_same_v<T, ResourceTransferMutationConfig>) {
          return std::make_unique<ResourceTransferMutation>(cfg);
        } else if constexpr (std::is_same_v<T, ClearInventoryMutationConfig>) {
          return std::make_unique<ClearInventoryMutation>(cfg);
        } else if constexpr (std::is_same_v<T, AttackMutationConfig>) {
          return std::make_unique<AttackMutation>(cfg);
        } else if constexpr (std::is_same_v<T, StatsMutationConfig>) {
          return std::make_unique<StatsMutation>(cfg);
        } else if constexpr (std::is_same_v<T, AddTagMutationConfig>) {
          return std::make_unique<AddTagMutation>(cfg);
        } else if constexpr (std::is_same_v<T, RemoveTagMutationConfig>) {
          return std::make_unique<RemoveTagMutation>(cfg);
        } else if constexpr (std::is_same_v<T, GameValueMutationConfig>) {
          return std::make_unique<GameValueMutation>(cfg);
        } else if constexpr (std::is_same_v<T, RecomputeMaterializedQueryMutationConfig>) {
          return std::make_unique<RecomputeMaterializedQueryMutation>(cfg);
        } else if constexpr (std::is_same_v<T, QueryInventoryMutationConfig>) {
          return std::make_unique<QueryInventoryMutation>(cfg);
        } else if constexpr (std::is_same_v<T, RemoveTagsWithPrefixMutationConfig>) {
          return std::make_unique<RemoveTagsWithPrefixMutation>(cfg);
        } else if constexpr (std::is_same_v<T, RelocateMutationConfig>) {
          return std::make_unique<RelocateMutation>(cfg);
        } else if constexpr (std::is_same_v<T, SwapMutationConfig>) {
          return std::make_unique<SwapMutation>(cfg);
        } else if constexpr (std::is_same_v<T, UseTargetMutationConfig>) {
          return std::make_unique<UseTargetMutation>(cfg);
        } else if constexpr (std::is_same_v<T, SpawnObjectMutationConfig>) {
          return std::make_unique<SpawnObjectMutation>(cfg);
        } else if constexpr (std::is_same_v<T, RaycastSpawnMutationConfig>) {
          return std::make_unique<RaycastSpawnMutation>(cfg);
        } else if constexpr (std::is_same_v<T, ChangeVibeMutationConfig>) {
          return std::make_unique<ChangeVibeMutation>(cfg);
        } else {
          return nullptr;
        }
      },
      config);
}

}  // namespace mettagrid
