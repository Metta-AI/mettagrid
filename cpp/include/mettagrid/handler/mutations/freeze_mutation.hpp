#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_FREEZE_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_FREEZE_MUTATION_HPP_

#include "handler/handler_config.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation.hpp"

namespace mettagrid {

/**
 * FreezeMutation: Freeze target for duration
 * Note: This requires the target to have a freeze mechanism.
 * For now, this is a stub that would need integration with agent freeze system.
 */
class FreezeMutation : public Mutation {
public:
  explicit FreezeMutation(const FreezeMutationConfig& config) : _config(config) {}

  void apply(HandlerContext& ctx) override {
    // TODO: Integrate with agent freeze system
    // For now, this is a placeholder
    (void)ctx;
    (void)_config;
  }

private:
  FreezeMutationConfig _config;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_FREEZE_MUTATION_HPP_
