#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_TARGET_LOC_EMPTY_FILTER_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_TARGET_LOC_EMPTY_FILTER_HPP_

#include "core/filter_config.hpp"
#include "handler/filters/filter.hpp"
#include "handler/handler_context.hpp"

namespace mettagrid {

class TargetLocEmptyFilter : public Filter {
public:
  explicit TargetLocEmptyFilter(const TargetLocEmptyFilterConfig& /*config*/) {}

  bool passes(const HandlerContext& ctx) const override {
    return ctx.target == nullptr;
  }
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_TARGET_LOC_EMPTY_FILTER_HPP_
