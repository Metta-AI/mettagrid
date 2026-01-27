#include "handler/handler.hpp"

#include "handler/filters/filter_factory.hpp"
#include "handler/mutations/mutation_factory.hpp"

namespace mettagrid {

Handler::Handler(const HandlerConfig& config, TagIndex* tag_index) : _name(config.name), _radius(config.radius) {
  // Create filters from config
  for (const auto& filter_config : config.filters) {
    auto filter = create_filter(filter_config, tag_index);
    if (filter) {
      _filters.push_back(std::move(filter));
    }
  }

  // Create mutations from config using shared factory
  for (const auto& mutation_config : config.mutations) {
    auto mutation = create_mutation(mutation_config);
    if (mutation) {
      _mutations.push_back(std::move(mutation));
    }
  }
}

bool Handler::try_apply(HandlerContext& ctx) {
  if (!check_filters(ctx)) {
    return false;
  }

  for (auto& mutation : _mutations) {
    mutation->apply(ctx);
  }

  return true;
}

bool Handler::try_apply(HasInventory* actor, HasInventory* target) {
  HandlerContext ctx(actor, target);
  return try_apply(ctx);
}

bool Handler::check_filters(const HandlerContext& ctx) const {
  for (const auto& filter : _filters) {
    if (!filter->passes(ctx)) {
      return false;
    }
  }

  return true;
}

bool Handler::check_filters(HasInventory* actor, HasInventory* target) const {
  HandlerContext ctx(actor, target);
  return check_filters(ctx);
}

}  // namespace mettagrid
