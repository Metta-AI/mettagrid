#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_MUTATION_HPP_

#include "handler/handler_context.hpp"

namespace mettagrid {

/**
 * Base interface for handler mutations.
 * Mutations modify state when a handler triggers.
 */
class Mutation {
public:
  virtual ~Mutation() = default;

  // Apply the mutation to the context
  virtual void apply(HandlerContext& ctx) = 0;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_MUTATION_HPP_
