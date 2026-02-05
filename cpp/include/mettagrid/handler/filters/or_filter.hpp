#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_OR_FILTER_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_OR_FILTER_HPP_

#include <memory>
#include <vector>

#include "handler/filters/filter.hpp"

namespace mettagrid {

/**
 * OrFilter: Passes if ANY of the inner filters pass.
 *
 * This implements OR(A, B, C, ...) semantics - returns true on the first
 * inner filter that passes (short-circuit evaluation).
 */
class OrFilter : public Filter {
public:
  explicit OrFilter(std::vector<std::unique_ptr<Filter>> inner) : _inner(std::move(inner)) {}

  bool passes(const HandlerContext& ctx) const override {
    // Return true if ANY inner filter passes
    for (const auto& filter : _inner) {
      if (filter->passes(ctx)) {
        return true;
      }
    }
    // No inner filter passed
    return false;
  }

private:
  std::vector<std::unique_ptr<Filter>> _inner;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_OR_FILTER_HPP_
