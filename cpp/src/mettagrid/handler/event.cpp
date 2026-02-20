#include "handler/event.hpp"

#include <algorithm>

#include "core/tag_index.hpp"
#include "handler/filters/filter_factory.hpp"
#include "handler/mutations/mutation_factory.hpp"

namespace mettagrid {

Event::Event(const EventConfig& config)
    : _name(config.name),
      _target_tag_id(config.target_tag_id),
      _max_targets(config.max_targets),
      _fallback_name(config.fallback) {
  // Create filters from config using shared factory
  for (const auto& filter_config : config.filters) {
    auto filter = create_filter(filter_config);
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

int Event::execute(const HandlerContext& ctx) {
  // Find targets by tag
  std::vector<GridObject*> targets;
  const auto& objects = ctx.tag_index->get_objects_with_tag(_target_tag_id);
  for (auto* obj : objects) {
    targets.push_back(obj);
  }

  // If max_targets is limited and we have more candidates than needed, shuffle
  if (_max_targets > 0 && targets.size() > static_cast<size_t>(_max_targets)) {
    std::shuffle(targets.begin(), targets.end(), *ctx.rng);
  }

  // Apply to targets, respecting max_targets limit
  int targets_applied = 0;
  for (auto* target : targets) {
    if (_max_targets > 0 && targets_applied >= _max_targets) {
      break;
    }
    if (try_apply(target, ctx)) {
      ++targets_applied;
    }
  }

  // If no targets matched and we have a fallback, execute it instead
  if (targets_applied == 0 && _fallback_event != nullptr) {
    return _fallback_event->execute(ctx);
  }

  return targets_applied;
}

bool Event::try_apply(GridObject* target, const HandlerContext& ctx) {
  HandlerContext target_ctx = ctx;
  target_ctx.actor = target;
  target_ctx.target = target;

  if (!check_filters(target, target_ctx)) {
    return false;
  }

  for (auto& mutation : _mutations) {
    mutation->apply(target_ctx);
  }

  return true;
}

bool Event::check_filters(GridObject* target, const HandlerContext& ctx) const {
  HandlerContext target_ctx = ctx;
  target_ctx.actor = target;
  target_ctx.target = target;

  for (const auto& filter : _filters) {
    if (!filter->passes(target_ctx)) {
      return false;
    }
  }

  return true;
}

}  // namespace mettagrid
