#include "handler/handler.hpp"

#include <cassert>
#include <cstdlib>
#include <iostream>
#include <string_view>

#include "handler/filters/filter_factory.hpp"
#include "handler/mutations/mutation_factory.hpp"

namespace mettagrid {

namespace {

bool debug_handlers_enabled() {
  static const bool enabled = []() {
    const char* value = std::getenv("DEBUG_HANDLERS");
    return value != nullptr && std::string_view(value) == "1";
  }();
  return enabled;
}

void append_entity_debug_format(std::ostream& stream, const GridObject* object) {
  if (object == nullptr) {
    stream << "none";
    return;
  }

  if (!object->type_name.empty()) {
    stream << object->type_name << ':';
  }
  if (!object->name.empty()) {
    stream << object->name;
  }
  stream << '(' << object->id << ')';
}

void log_handler_result(const std::string& handler_name, const HandlerContext& ctx, bool succeeded) {
  if (!debug_handlers_enabled()) {
    return;
  }

  const std::string_view display_name =
      handler_name.empty() ? std::string_view("<unnamed>") : std::string_view(handler_name);

  std::cout << "[DEBUG_HANDLERS] " << display_name << '(';
  append_entity_debug_format(std::cout, ctx.actor);
  std::cout << " -> ";
  append_entity_debug_format(std::cout, ctx.target);
  std::cout << ") = " << (succeeded ? "success" : "fail");
  std::cout << std::endl;
}

}  // namespace

Handler::Handler(const HandlerConfig& config) : _name(config.name) {
  assert(!_name.empty() && "Handler name must not be empty");

  // Create filters from config
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

bool Handler::try_apply(HandlerContext& ctx) {
  if (!check_filters(ctx)) {
    log_handler_result(_name, ctx, false);
    return false;
  }

  for (auto& mutation : _mutations) {
    mutation->apply(ctx);
  }

  log_handler_result(_name, ctx, true);
  return true;
}

bool Handler::try_apply(GridObject* actor, GridObject* target) {
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

bool Handler::check_filters(GridObject* actor, GridObject* target) const {
  HandlerContext ctx(actor, target);
  return check_filters(ctx);
}

}  // namespace mettagrid
