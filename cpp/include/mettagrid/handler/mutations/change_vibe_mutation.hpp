#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_CHANGE_VIBE_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_CHANGE_VIBE_MUTATION_HPP_

#include "core/grid_object.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation.hpp"

namespace mettagrid {

class ChangeVibeMutation : public Mutation {
public:
  explicit ChangeVibeMutation(const ChangeVibeMutationConfig& config) : _config(config) {}

  void apply(HandlerContext& ctx) override {
    GridObject* obj = dynamic_cast<GridObject*>(ctx.resolve(_config.entity));
    if (obj != nullptr) {
      obj->set_vibe(_config.vibe_id);
    }
  }

private:
  ChangeVibeMutationConfig _config;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_CHANGE_VIBE_MUTATION_HPP_
