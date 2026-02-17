#include "handler/multi_handler.hpp"

namespace mettagrid {

MultiHandler::MultiHandler(std::vector<std::shared_ptr<Handler>> handlers, HandlerMode mode)
    : Handler(HandlerConfig("multi_handler")), _handlers(std::move(handlers)), _mode(mode) {}

bool MultiHandler::try_apply(HandlerContext& ctx) {
  bool any_applied = false;

  for (auto& handler : _handlers) {
    if (handler->try_apply(ctx)) {
      any_applied = true;
      if (_mode == HandlerMode::FirstMatch) {
        return true;  // Stop on first success
      }
    }
  }

  return any_applied;
}

}  // namespace mettagrid
