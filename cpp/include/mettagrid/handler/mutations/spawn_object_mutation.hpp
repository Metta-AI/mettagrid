#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_SPAWN_OBJECT_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_SPAWN_OBJECT_MUTATION_HPP_

#include <string>

#include "core/mutation_config.hpp"
#include "handler/mutations/mutation.hpp"

namespace mettagrid {

class SpawnObjectMutation : public Mutation {
public:
  explicit SpawnObjectMutation(const SpawnObjectMutationConfig& config) : _object_type(config.object_type) {}

  void apply(HandlerContext& ctx) override;

private:
  std::string _object_type;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_SPAWN_OBJECT_MUTATION_HPP_
