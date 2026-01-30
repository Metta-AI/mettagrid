#include "core/tag_index.hpp"

#include "core/grid_object.hpp"

namespace mettagrid {

const std::vector<GridObject*> TagIndex::_empty{};

void TagIndex::register_object(GridObject* obj) {
  if (obj == nullptr) return;
  for (int tag_id : obj->tag_ids) {
    _objects_by_tag[tag_id].push_back(obj);
    _counts_by_tag[tag_id] = static_cast<float>(_objects_by_tag[tag_id].size());
  }
}

void TagIndex::unregister_object(GridObject* obj) {
  if (obj == nullptr) return;
  for (int tag_id : obj->tag_ids) {
    auto& vec = _objects_by_tag[tag_id];
    vec.erase(std::remove(vec.begin(), vec.end(), obj), vec.end());
    _counts_by_tag[tag_id] = static_cast<float>(vec.size());
  }
}

void TagIndex::on_tag_added(GridObject* obj, int tag_id) {
  if (obj == nullptr) return;
  _objects_by_tag[tag_id].push_back(obj);
  _counts_by_tag[tag_id] = static_cast<float>(_objects_by_tag[tag_id].size());
}

void TagIndex::on_tag_removed(GridObject* obj, int tag_id) {
  if (obj == nullptr) return;
  auto& vec = _objects_by_tag[tag_id];
  vec.erase(std::remove(vec.begin(), vec.end(), obj), vec.end());
  _counts_by_tag[tag_id] = static_cast<float>(vec.size());
}

const std::vector<GridObject*>& TagIndex::get_objects_with_tag(int tag_id) const {
  auto it = _objects_by_tag.find(tag_id);
  if (it != _objects_by_tag.end()) {
    return it->second;
  }
  return _empty;
}

size_t TagIndex::count_objects_with_tag(int tag_id) const {
  auto it = _objects_by_tag.find(tag_id);
  if (it != _objects_by_tag.end()) {
    return it->second.size();
  }
  return 0;
}

float* TagIndex::get_count_ptr(int tag_id) {
  return &_counts_by_tag[tag_id];
}

}  // namespace mettagrid
