#include "handler/filters/filter_factory.hpp"

#include <type_traits>

#include "handler/filters/alignment_filter.hpp"
#include "handler/filters/game_value_filter.hpp"
#include "handler/filters/near_filter.hpp"
#include "handler/filters/resource_filter.hpp"
#include "handler/filters/tag_filter.hpp"
#include "handler/filters/vibe_filter.hpp"

namespace mettagrid {

std::unique_ptr<Filter> create_filter(const FilterConfig& config, TagIndex* tag_index) {
  return std::visit(
      [tag_index](auto&& cfg) -> std::unique_ptr<Filter> {
        using T = std::decay_t<decltype(cfg)>;
        if constexpr (std::is_same_v<T, VibeFilterConfig>) {
          return std::make_unique<VibeFilter>(cfg);
        } else if constexpr (std::is_same_v<T, ResourceFilterConfig>) {
          return std::make_unique<ResourceFilter>(cfg);
        } else if constexpr (std::is_same_v<T, AlignmentFilterConfig>) {
          return std::make_unique<AlignmentFilter>(cfg);
        } else if constexpr (std::is_same_v<T, TagFilterConfig>) {
          return std::make_unique<TagFilter>(cfg);
        } else if constexpr (std::is_same_v<T, NearFilterConfig>) {
          std::vector<std::unique_ptr<Filter>> filters;
          for (const auto& filter_cfg : cfg.filters) {
            auto filter = create_filter(filter_cfg, tag_index);
            if (filter) {
              filters.push_back(std::move(filter));
            }
          }
          return std::make_unique<NearFilter>(cfg, std::move(filters));
        } else if constexpr (std::is_same_v<T, GameValueFilterConfig>) {
          return std::make_unique<GameValueFilter>(cfg);
        } else {
          return nullptr;
        }
      },
      config);
}

}  // namespace mettagrid
