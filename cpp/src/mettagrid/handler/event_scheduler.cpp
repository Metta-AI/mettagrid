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

  // Resolve fallback event pointers (after all events are created)
  for (auto& [name, event] : _events) {
    const auto& fallback_name = event->fallback_name();
    if (!fallback_name.empty()) {
      Event* fallback = get_event(fallback_name);
      event->set_fallback_event(fallback);
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

    // Execute event (handles fallback internally if no targets match)
    int targets_applied = event->execute(tag_index, _rng);
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

void EventScheduler::set_grid(Grid* grid) {
  for (auto& [name, event] : _events) {
    event->set_grid(grid);
  }
}

}  // namespace mettagrid
