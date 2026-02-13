#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_SHARED_TAG_FILTER_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_SHARED_TAG_FILTER_HPP_

#include "core/grid_object.hpp"
#include "handler/filters/filter.hpp"
#include "handler/handler_config.hpp"

namespace mettagrid {

/**
 * SharedTagPrefixFilter: passes when actor and target share at least one tag
 * from a prefix group (e.g. "team:red", "team:blue").
 *
 * _mask has bits set for all tag IDs matching the prefix (resolved at config time).
 */
class SharedTagPrefixFilter : public Filter {
public:
  explicit SharedTagPrefixFilter(const SharedTagPrefixFilterConfig& config) {
    for (int tag_id : config.tag_ids) {
      _mask.set(tag_id);
    }
  }

  bool passes(const HandlerContext& ctx) const override {
    auto actor_masked = masked_tags(ctx, EntityRef::actor);
    auto target_masked = masked_tags(ctx, EntityRef::target);
    return (actor_masked & target_masked).any();
  }

private:
  std::bitset<kMaxTags> masked_tags(const HandlerContext& ctx, EntityRef ref) const {
    GridObject* obj = dynamic_cast<GridObject*>(ctx.resolve(ref));
    if (obj == nullptr) return {};
    return obj->tag_bits & _mask;
  }

  std::bitset<kMaxTags> _mask;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_FILTERS_SHARED_TAG_FILTER_HPP_
