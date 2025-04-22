#ifndef GRID_HPP
#define GRID_HPP

#include <algorithm>
#include <vector>

#include "cpp_grid_object.hpp"

using namespace std;
typedef vector<vector<vector<cpp_GridObjectId> > > GridType;

class Grid {
public:
    unsigned int width;
    unsigned int height;
    vector<cpp_Layer> layer_for_type_id;
    cpp_Layer num_layers;

    GridType grid;
    vector<CppGridObject*> objects;

    inline Grid(unsigned int width, unsigned int height, vector<cpp_Layer> layer_for_type_id)
        : width(width), height(height), layer_for_type_id(layer_for_type_id)
    {
        num_layers = *max_element(layer_for_type_id.begin(), layer_for_type_id.end()) + 1;
        grid.resize(height, vector<vector<cpp_GridObjectId> >(width, vector<cpp_GridObjectId>(this->num_layers, 0)));

        // 0 is reserved for empty space
        objects.push_back(nullptr);
    }

    inline ~Grid()
    {
        for (unsigned long id = 1; id < objects.size(); ++id) {
            if (objects[id] != nullptr) {
                delete objects[id];
            }
        }
    }

    inline char add_object(CppGridObject* obj)
    {
        if (obj->location.row >= height or obj->location.col >= width or obj->location.layer >= num_layers) {
            return false;
        }
        if (this->grid[obj->location.row][obj->location.col][obj->location.layer] != 0) {
            return false;
        }

        obj->id = this->objects.size();
        this->objects.push_back(obj);
        this->grid[obj->location.row][obj->location.col][obj->location.layer] = obj->id;
        return true;
    }

    inline void remove_object(CppGridObject* obj)
    {
        this->grid[obj->location.row][obj->location.col][obj->location.layer] = 0;
        // delete obj;
        this->objects[obj->id] = nullptr;
    }

    inline void remove_object(cpp_GridObjectId id)
    {
        CppGridObject* obj = this->objects[id];
        this->remove_object(obj);
    }

    inline char move_object(cpp_GridObjectId id, const CppGridLocation& loc)
    {
        if (loc.row >= height or loc.col >= width or loc.layer >= num_layers) {
            return false;
        }

        if (grid[loc.row][loc.col][loc.layer] != 0) {
            return false;
        }

        CppGridObject* obj = objects[id];
        grid[loc.row][loc.col][loc.layer] = id;
        grid[obj->location.row][obj->location.col][obj->location.layer] = 0;
        obj->location = loc;
        return true;
    }

    inline void swap_objects(cpp_GridObjectId id1, cpp_GridObjectId id2)
    {
        CppGridObject* obj1 = objects[id1];
        CppGridLocation loc1 = obj1->location;
        cpp_Layer layer1 = loc1.layer;
        grid[loc1.row][loc1.col][loc1.layer] = 0;

        CppGridObject* obj2 = objects[id2];
        CppGridLocation loc2 = obj2->location;
        cpp_Layer layer2 = loc2.layer;
        grid[loc2.row][loc2.col][loc2.layer] = 0;

        // Keep the layer the same
        obj1->location = loc2;
        obj1->location.layer = layer1;
        obj2->location = loc1;
        obj2->location.layer = layer2;

        grid[obj1->location.row][obj1->location.col][obj1->location.layer] = id1;
        grid[obj2->location.row][obj2->location.col][obj2->location.layer] = id2;
    }

    inline CppGridObject* object(cpp_GridObjectId obj_id)
    {
        return objects[obj_id];
    }

    inline CppGridObject* object_at(const CppGridLocation& loc)
    {
        if (loc.row >= height or loc.col >= width or loc.layer >= num_layers) {
            return nullptr;
        }
        if (grid[loc.row][loc.col][loc.layer] == 0) {
            return nullptr;
        }
        return objects[grid[loc.row][loc.col][loc.layer]];
    }

    inline CppGridObject* object_at(const CppGridLocation& loc, cpp_TypeId type_id)
    {
        CppGridObject* obj = object_at(loc);
        if (obj != NULL and obj->objectTypeId == type_id) {
            return obj;
        }
        return nullptr;
    }

    inline CppGridObject* object_at(cpp_GridCoord r, cpp_GridCoord c, cpp_TypeId type_id)
    {
        CppGridObject* obj = object_at(CppGridLocation(r, c), this->layer_for_type_id[type_id]);
        if (obj->objectTypeId != type_id) {
            return nullptr;
        }

        return obj;
    }

    inline const CppGridLocation location(cpp_GridObjectId id)
    {
        return objects[id]->location;
    }

    inline const CppGridLocation relative_location(const CppGridLocation& loc, cpp_Orientation orientation,
                                                   cpp_GridCoord distance, cpp_GridCoord offset)
    {
        int new_r = loc.row;
        int new_c = loc.col;

        switch (orientation) {
            case Up:
                new_r = loc.row - distance;
                new_c = loc.col - offset;
                break;
            case Down:
                new_r = loc.row + distance;
                new_c = loc.col + offset;
                break;
            case Left:
                new_r = loc.row + offset;
                new_c = loc.col - distance;
                break;
            case Right:
                new_r = loc.row - offset;
                new_c = loc.col + distance;
                break;
        }
        new_r = max(0, new_r);
        new_c = max(0, new_c);
        return CppGridLocation(new_r, new_c, loc.layer);
    }

    inline const CppGridLocation relative_location(const CppGridLocation& loc, cpp_Orientation orientation,
                                                   cpp_GridCoord distance, cpp_GridCoord offset, cpp_TypeId type_id)
    {
        CppGridLocation rloc = this->relative_location(loc, orientation, distance, offset);
        rloc.layer = this->layer_for_type_id[type_id];
        return rloc;
    }

    inline const CppGridLocation relative_location(const CppGridLocation& loc, cpp_Orientation orientation)
    {
        return this->relative_location(loc, orientation, 1, 0);
    }

    inline const CppGridLocation relative_location(const CppGridLocation& loc, cpp_Orientation orientation,
                                                   cpp_TypeId type_id)
    {
        return this->relative_location(loc, orientation, 1, 0, type_id);
    }

    inline char is_empty(unsigned int row, unsigned int col)
    {
        CppGridLocation loc;
        loc.row = row;
        loc.col = col;
        for (int layer = 0; layer < num_layers; ++layer) {
            loc.layer = layer;
            if (object_at(loc) != nullptr) {
                return 0;
            }
        }
        return 1;
    }
};

#endif  // GRID_HPP