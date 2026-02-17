#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_TAG_MUTATION_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_TAG_MUTATION_HPP_

#include <cassert>

#include "core/grid_object.hpp"
#include "handler/handler_config.hpp"
#include "handler/handler_context.hpp"
#include "handler/mutations/mutation.hpp"

namespace mettagrid {

/**
 * AddTagMutation: Add a tag to an entity
 */
class AddTagMutation : public Mutation {
public:
  explicit AddTagMutation(const AddTagMutationConfig& config) : _config(config) {}

  void apply(HandlerContext& ctx) override {
    GridObject* obj = dynamic_cast<GridObject*>(ctx.resolve(_config.entity));
    if (obj != nullptr) {
      obj->add_tag(_config.tag_id, ctx);
    }
  }

private:
  AddTagMutationConfig _config;
};

/**
 * RemoveTagMutation: Remove a tag from an entity
 */
class RemoveTagMutation : public Mutation {
public:
  explicit RemoveTagMutation(const RemoveTagMutationConfig& config) : _config(config) {}

  void apply(HandlerContext& ctx) override {
    GridObject* obj = dynamic_cast<GridObject*>(ctx.resolve(_config.entity));
    if (obj != nullptr) {
      obj->remove_tag(_config.tag_id, ctx);
    }
  }

private:
  RemoveTagMutationConfig _config;
};

/**
 * RemoveTagsWithPrefixMutation: Remove all tags matching a prefix from an entity.
 * Used for cascading tag cleanup (e.g., removing team tags when connectivity lost).
 */
class RemoveTagsWithPrefixMutation : public Mutation {
public:
  explicit RemoveTagsWithPrefixMutation(const RemoveTagsWithPrefixMutationConfig& config) : _config(config) {}

  void apply(HandlerContext& ctx) override {
    GridObject* obj = dynamic_cast<GridObject*>(ctx.resolve(_config.entity));
    assert(obj != nullptr);
    for (int tag_id : _config.tag_ids) {
      obj->remove_tag(tag_id, ctx);
    }
  }

private:
  RemoveTagsWithPrefixMutationConfig _config;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_HANDLER_MUTATIONS_TAG_MUTATION_HPP_
