#include "handler/event.hpp"

#include "core/tag_index.hpp"
#include "handler/filters/filter_factory.hpp"
#include "handler/mutations/mutation_factory.hpp"

namespace mettagrid {

Event::Event(const EventConfig& config, TagIndex* tag_index)
    : _name(config.name),
      _target_tag_id(config.target_tag_id),
      _max_targets(config.max_targets),
      _tag_index(tag_index) {
  // Create filters from config using shared factory
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

bool Event::try_apply(HasInventory* target) {
  // For events, there's no actor - the target is the only entity
  // Pass collectives in context for runtime resolution
  HandlerContext ctx(nullptr, target, nullptr, _tag_index, _collectives);

  if (!check_filters(target)) {
    return false;
  }

  for (auto& mutation : _mutations) {
    mutation->apply(ctx);
  }

  return true;
}

bool Event::check_filters(HasInventory* target) const {
  // For events, there's no actor - the target is the only entity
  // Pass collectives in context for runtime resolution
  HandlerContext ctx(nullptr, target, nullptr, _tag_index, _collectives);

  for (const auto& filter : _filters) {
    if (!filter->passes(ctx)) {
      return false;
    }
  }

  return true;
}

}  // namespace mettagrid
