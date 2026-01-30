#include "handler/mutations/mutation_factory.hpp"

#include <type_traits>

#include "handler/mutations/alignment_mutation.hpp"
#include "handler/mutations/attack_mutation.hpp"
#include "handler/mutations/freeze_mutation.hpp"
#include "handler/mutations/game_value_mutation.hpp"
#include "handler/mutations/resource_mutation.hpp"
#include "handler/mutations/stats_mutation.hpp"
#include "handler/mutations/tag_mutation.hpp"

namespace mettagrid {

std::unique_ptr<Mutation> create_mutation(const MutationConfig& config) {
  return std::visit(
      [](auto&& cfg) -> std::unique_ptr<Mutation> {
        using T = std::decay_t<decltype(cfg)>;
        if constexpr (std::is_same_v<T, ResourceDeltaMutationConfig>) {
          return std::make_unique<ResourceDeltaMutation>(cfg);
        } else if constexpr (std::is_same_v<T, ResourceTransferMutationConfig>) {
          return std::make_unique<ResourceTransferMutation>(cfg);
        } else if constexpr (std::is_same_v<T, AlignmentMutationConfig>) {
          return std::make_unique<AlignmentMutation>(cfg);
        } else if constexpr (std::is_same_v<T, FreezeMutationConfig>) {
          return std::make_unique<FreezeMutation>(cfg);
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
        } else {
          return nullptr;
        }
      },
      config);
}

}  // namespace mettagrid
