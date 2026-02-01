#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_NEG_FILTER_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_NEG_FILTER_HPP_

#include <memory>
#include <vector>

#include "handler/filters/filter.hpp"

namespace mettagrid {

/**
 * NegFilter: Negates the result of inner filter(s).
 *
 * If multiple inner filters are provided, they are ANDed together first,
 * then the result is negated. This implements NOT(A AND B AND ...).
 *
 * This is critical for correct semantics when negating multi-resource filters:
 * - isNot(targetHas({"gold": 1, "key": 1})) should pass if target lacks EITHER resource
 * - NOT (gold >= 1 AND key >= 1) = (NOT gold >= 1) OR (NOT key >= 1)
 */
class NegFilter : public Filter {
public:
  explicit NegFilter(std::vector<std::unique_ptr<Filter>> inner) : _inner(std::move(inner)) {}

  // Convenience constructor for a single inner filter.
  explicit NegFilter(std::unique_ptr<Filter> single) {
    _inner.push_back(std::move(single));
  }

  bool passes(const HandlerContext& ctx) const override {
    // AND all inner filters, then negate
    for (const auto& filter : _inner) {
      if (!filter->passes(ctx)) {
        // Inner filter failed, so AND result is false, negation is true
        return true;
      }
    }
    // All inner filters passed, so AND result is true, negation is false
    return false;
  }

private:
  std::vector<std::unique_ptr<Filter>> _inner;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_NEG_FILTER_HPP_
