#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_FILTER_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_FILTER_HPP_

#include "handler/handler_context.hpp"

namespace mettagrid {

/**
 * Base interface for handler filters.
 * Filters determine whether a handler should trigger.
 */
class Filter {
public:
  virtual ~Filter() = default;

  // Returns true if the handler passes this filter
  virtual bool passes(const HandlerContext& ctx) const = 0;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_FILTER_HPP_
