#include "handler/filters/filter_factory.hpp"

#include <cassert>
#include <type_traits>

#include "handler/filters/alignment_filter.hpp"
#include "handler/filters/game_value_filter.hpp"
#include "handler/filters/max_distance_filter.hpp"
#include "handler/filters/neg_filter.hpp"
#include "handler/filters/or_filter.hpp"
#include "handler/filters/query_resource_filter.hpp"
#include "handler/filters/resource_filter.hpp"
#include "handler/filters/shared_tag_filter.hpp"
#include "handler/filters/vibe_filter.hpp"

namespace mettagrid {

std::unique_ptr<Filter> create_filter(const FilterConfig& config) {
  return std::visit(
      [](auto&& cfg) -> std::unique_ptr<Filter> {
        using T = std::decay_t<decltype(cfg)>;
        if constexpr (std::is_same_v<T, VibeFilterConfig>) {
          return std::make_unique<VibeFilter>(cfg);
        } else if constexpr (std::is_same_v<T, ResourceFilterConfig>) {
          return std::make_unique<ResourceFilter>(cfg);
        } else if constexpr (std::is_same_v<T, AlignmentFilterConfig>) {
          return std::make_unique<AlignmentFilter>(cfg);
        } else if constexpr (std::is_same_v<T, SharedTagPrefixFilterConfig>) {
          return std::make_unique<SharedTagPrefixFilter>(cfg);
        } else if constexpr (std::is_same_v<T, TagPrefixFilterConfig>) {
          return std::make_unique<TagPrefixFilter>(cfg);
        } else if constexpr (std::is_same_v<T, GameValueFilterConfig>) {
          return std::make_unique<GameValueFilter>(cfg);
        } else if constexpr (std::is_same_v<T, NegFilterConfig>) {
          // NegFilter supports multiple inner filters that are ANDed, then negated.
          // This correctly handles NOT(A AND B) semantics for multi-resource filters.
          std::vector<std::unique_ptr<Filter>> inner_filters;
          for (const auto& inner_cfg : cfg.inner) {
            auto filter = create_filter(inner_cfg);
            if (filter) {
              inner_filters.push_back(std::move(filter));
            }
          }
          return std::make_unique<NegFilter>(std::move(inner_filters));
        } else if constexpr (std::is_same_v<T, MaxDistanceFilterConfig>) {
          return std::make_unique<MaxDistanceFilter>(cfg);
        } else if constexpr (std::is_same_v<T, QueryResourceFilterConfig>) {
          return std::make_unique<QueryResourceFilter>(cfg);
        } else if constexpr (std::is_same_v<T, OrFilterConfig>) {
          // OrFilter: passes if ANY inner filter passes
          std::vector<std::unique_ptr<Filter>> inner_filters;
          for (const auto& inner_cfg : cfg.inner) {
            auto filter = create_filter(inner_cfg);
            if (filter) {
              inner_filters.push_back(std::move(filter));
            }
          }
          return std::make_unique<OrFilter>(std::move(inner_filters));
        } else {
          return nullptr;
        }
      },
      config);
}

}  // namespace mettagrid
