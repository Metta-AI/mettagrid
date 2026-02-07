#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_HANDLER_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_HANDLER_HPP_

#include <memory>
#include <string>
#include <variant>
#include <vector>

#include "core/tag_index.hpp"
#include "handler/filters/filter.hpp"
#include "handler/handler_config.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation.hpp"

namespace mettagrid {

/**
 * Handler processes events through configurable filter chains and mutation chains.
 *
 * Used for two handler types:
 *   - on_use: Triggered when agent uses/activates an object
 *   - aoe: Triggered per-tick for objects within radius
 *
 * Usage:
 *   1. Create handler with HandlerConfig
 *   2. Call try_apply() with appropriate context
 *   3. Returns true if all filters passed and mutations were applied
 *
 * This is a virtual base class; MultiHandler also inherits from Handler.
 */
class Handler {
public:
  explicit Handler(const HandlerConfig& config, TagIndex* tag_index = nullptr);
  virtual ~Handler() = default;

  // Get handler name
  const std::string& name() const {
    return _name;
  }

  // Try to apply this handler with the given context
  // Returns true if all filters passed and mutations were applied
  virtual bool try_apply(HandlerContext& ctx);

  // Try to apply this handler to the given actor and target
  // Returns true if all filters passed and mutations were applied
  bool try_apply(HasInventory* actor, HasInventory* target);

  // Check if all filters pass without applying mutations
  bool check_filters(const HandlerContext& ctx) const;

  // Check if all filters pass without applying mutations
  bool check_filters(HasInventory* actor, HasInventory* target) const;

private:
  std::string _name;
  std::vector<std::unique_ptr<Filter>> _filters;
  std::vector<std::unique_ptr<Mutation>> _mutations;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_HANDLER_HPP_
