#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_FILTER_FACTORY_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_FILTER_FACTORY_HPP_

#include <memory>

#include "core/tag_index.hpp"
#include "handler/filters/filter.hpp"
#include "handler/handler_config.hpp"

namespace mettagrid {

// Create a filter from its config variant
std::unique_ptr<Filter> create_filter(const FilterConfig& config, TagIndex* tag_index = nullptr);

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_FILTER_FACTORY_HPP_
