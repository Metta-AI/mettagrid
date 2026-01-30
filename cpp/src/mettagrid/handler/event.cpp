#include "handler/event.hpp"

#include <algorithm>

#include "core/tag_index.hpp"
#include "handler/filters/filter_factory.hpp"
#include "handler/mutations/mutation_factory.hpp"

namespace mettagrid {

Event::Event(const EventConfig& config, TagIndex* tag_index)
    : _name(config.name),
      _target_tag_id(config.target_tag_id),
      _max_targets(config.max_targets),
      _fallback_name(config.fallback),
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

int Event::execute(TagIndex& tag_index, std::mt19937* rng) {
  // Find targets by tag
  std::vector<HasInventory*> targets;
  const auto& objects = tag_index.get_objects_with_tag(_target_tag_id);
  for (auto* obj : objects) {
    targets.push_back(obj);
  }

  // If max_targets is limited and we have more candidates than needed, shuffle
  if (_max_targets > 0 && targets.size() > static_cast<size_t>(_max_targets) && rng != nullptr) {
    std::shuffle(targets.begin(), targets.end(), *rng);
  }

  // Apply to targets, respecting max_targets limit
  int targets_applied = 0;
  for (auto* target : targets) {
    if (_max_targets > 0 && targets_applied >= _max_targets) {
      break;
    }
    if (try_apply(target)) {
      ++targets_applied;
    }
  }

  // If no targets matched and we have a fallback, execute it instead
  if (targets_applied == 0 && _fallback_event != nullptr) {
    return _fallback_event->execute(tag_index, rng);
  }

  return targets_applied;
}

bool Event::try_apply(HasInventory* target) {
  // For events, there's no actor - the target is the only entity
  // Pass collectives in context for runtime resolution
  HandlerContext ctx(nullptr, target, nullptr, _tag_index, _collectives);
  ctx.grid = _grid;

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
  ctx.grid = _grid;

  for (const auto& filter : _filters) {
    if (!filter->passes(ctx)) {
      return false;
    }
  }

  return true;
}

}  // namespace mettagrid
