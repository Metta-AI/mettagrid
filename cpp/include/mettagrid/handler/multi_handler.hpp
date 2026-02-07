#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MULTI_HANDLER_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MULTI_HANDLER_HPP_

#include <memory>
#include <vector>

#include "handler/handler.hpp"
#include "handler/handler_config.hpp"
#include "handler/handler_context.hpp"

namespace mettagrid {

/**
 * MultiHandler dispatches to multiple handlers with configurable mode.
 *
 * Modes:
 *   - FirstMatch: Try handlers in order, stop on first success (like on_use)
 *   - All: Apply all handlers where filters pass (like AOE)
 *
 * Usage:
 *   MultiHandler multi(handlers, HandlerMode::FirstMatch);
 *   bool any_applied = multi.try_apply(ctx);
 */
class MultiHandler : public Handler {
public:
  MultiHandler(std::vector<std::shared_ptr<Handler>> handlers, HandlerMode mode);

  // Try to apply handlers according to mode
  // Returns true if any handler was applied
  bool try_apply(HandlerContext& ctx) override;

  // Get the dispatch mode
  HandlerMode mode() const {
    return _mode;
  }

  // Check if empty
  bool empty() const {
    return _handlers.empty();
  }

  // Get handler count
  size_t size() const {
    return _handlers.size();
  }

private:
  std::vector<std::shared_ptr<Handler>> _handlers;
  HandlerMode _mode;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MULTI_HANDLER_HPP_
