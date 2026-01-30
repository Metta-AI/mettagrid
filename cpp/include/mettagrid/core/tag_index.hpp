#ifndef PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_TAG_INDEX_HPP_
#define PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_TAG_INDEX_HPP_

#include <algorithm>
#include <unordered_map>
#include <vector>

class GridObject;

namespace mettagrid {

class TagIndex {
public:
  TagIndex() = default;

  // Register object and index all its tags
  void register_object(GridObject* obj);

  // Unregister object and remove from all tag indices
  void unregister_object(GridObject* obj);

  // Called when a tag is added to an object
  void on_tag_added(GridObject* obj, int tag_id);

  // Called when a tag is removed from an object
  void on_tag_removed(GridObject* obj, int tag_id);

  // Get all objects with a specific tag
  const std::vector<GridObject*>& get_objects_with_tag(int tag_id) const;

  // Count objects with a specific tag
  size_t count_objects_with_tag(int tag_id) const;

  // Get pointer to the float count for a tag (creates entry if not exists)
  float* get_count_ptr(int tag_id);

private:
  std::unordered_map<int, std::vector<GridObject*>> _objects_by_tag;
  std::unordered_map<int, float> _counts_by_tag;
  static const std::vector<GridObject*> _empty;
};

}  // namespace mettagrid

#endif  // PACKAGES_METTAGRID_CPP_INCLUDE_METTAGRID_CORE_TAG_INDEX_HPP_
