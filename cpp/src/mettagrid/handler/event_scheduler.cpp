#include "handler/event_scheduler.hpp"

#include <algorithm>
#include <random>
#include <utility>

namespace mettagrid {

EventScheduler::EventScheduler(const std::map<std::string, EventConfig>& event_configs,
                               std::mt19937* rng,
                               TagIndex* tag_index)
    : _rng(rng) {
  // Create events and build the schedule
  for (const auto& [name, config] : event_configs) {
    auto event = std::make_unique<Event>(config, tag_index);
    Event* event_ptr = event.get();

    _events[name] = std::move(event);

    // Add all timesteps for this event to the schedule
    for (int timestep : config.timesteps) {
      _schedule.emplace_back(timestep, event_ptr);
    }
  }

  // Sort schedule by timestep
  std::sort(_schedule.begin(), _schedule.end(), [](const auto& a, const auto& b) { return a.first < b.first; });
}

int EventScheduler::process_timestep(int timestep, TagIndex& tag_index) {
  int events_fired = 0;

  // Process all events scheduled at or before the current timestep
  while (_next_idx < _schedule.size() && _schedule[_next_idx].first <= timestep) {
    Event* event = _schedule[_next_idx].second;

    // Use event's target_tag_id for efficient lookup via TagIndex
    int target_tag_id = event->target_tag_id();
    std::vector<HasInventory*> targets;
    const auto& objects = tag_index.get_objects_with_tag(target_tag_id);
    for (auto* obj : objects) {
      targets.push_back(obj);
    }

    // Apply event to each target, respecting max_targets limit
    int max_targets = event->max_targets();
    int targets_applied = 0;

    // If max_targets is limited and we have more candidates than needed,
    // shuffle to select targets randomly
    if (max_targets > 0 && targets.size() > static_cast<size_t>(max_targets) && _rng != nullptr) {
      std::shuffle(targets.begin(), targets.end(), *_rng);
    }

    for (auto* target : targets) {
      if (max_targets > 0 && targets_applied >= max_targets) {
        break;  // Reached the limit
      }
      if (event->try_apply(target)) {
        ++targets_applied;
      }
    }

    // Count this as one event fired if it was applied to at least one target
    if (targets_applied > 0) {
      ++events_fired;
    }

    _next_idx++;
  }

  return events_fired;
}

Event* EventScheduler::get_event(const std::string& name) {
  auto it = _events.find(name);
  if (it != _events.end()) {
    return it->second.get();
  }
  return nullptr;
}

void EventScheduler::set_collectives(const std::vector<std::unique_ptr<Collective>>* collectives) {
  for (auto& [name, event] : _events) {
    event->set_collectives(collectives);
  }
}

}  // namespace mettagrid
