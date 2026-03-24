#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_TARGET_IS_USABLE_FILTER_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_TARGET_IS_USABLE_FILTER_HPP_

#include "core/filter_config.hpp"
#include "handler/filters/filter.hpp"
#include "handler/handler_context.hpp"
#include "objects/usable.hpp"

namespace mettagrid {

class TargetIsUsableFilter : public Filter {
public:
  explicit TargetIsUsableFilter(const TargetIsUsableFilterConfig& /*config*/) {}

  bool passes(const HandlerContext& ctx) const override {
    if (!ctx.target) return false;
    return dynamic_cast<Usable*>(ctx.target) != nullptr;
  }
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_TARGET_IS_USABLE_FILTER_HPP_
