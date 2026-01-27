#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_MUTATION_FACTORY_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_MUTATION_FACTORY_HPP_

#include <memory>

#include "handler/handler_config.hpp"
#include "handler/mutations/mutation.hpp"

namespace mettagrid {

// Create a mutation from its config variant
std::unique_ptr<Mutation> create_mutation(const MutationConfig& config);

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_MUTATION_FACTORY_HPP_
