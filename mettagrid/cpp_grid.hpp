#ifndef CPP_GRID_HPP
#define CPP_GRID_HPP

#include <algorithm>
#include <vector>

#include "cpp_grid_object.hpp"

using namespace std;

// 3D grid: grid[row][col][layer] = object ID
typedef vector<vector<vector<cpp_GridObjectId>>> cpp_GridType;

/**
 * CppGrid represents a 3D grid of objects across (row, col, layer),
 * supporting object placement, movement, lookup, and spatial queries.
 */
class CppGrid {
public:
    unsigned int width;
    unsigned int height;
    vector<cpp_Layer> layer_for_type_id;
    cpp_Layer num_layers;

    cpp_GridType grid;               // Maps positions to object IDs
    vector<CppGridObject*> objects;  // Object store: index is ID

    /**
     * Construct a new grid of given dimensions and layer mapping.
     * Assumes that layer_for_type_id is non-empty and contains valid layers.
     */
    inline CppGrid(unsigned int width, unsigned int height, vector<cpp_Layer> layer_for_type_id)
        : width(width), height(height), layer_for_type_id(layer_for_type_id)
    {
        num_layers = *max_element(layer_for_type_id.begin(), layer_for_type_id.end()) + 1;
        grid.resize(height, vector<vector<cpp_GridObjectId>>(width, vector<cpp_GridObjectId>(num_layers, 0)));
        objects.push_back(nullptr);  // ID 0 reserved for empty
    }

    /**
     * Destructor: cleans up all non-null object pointers.
     */
    inline ~CppGrid()
    {
        for (unsigned long id = 1; id < objects.size(); ++id) {
            delete objects[id];
        }
    }

    /**
     * Attempt to add an object to the grid.
     * Returns true if successful, false if location is out-of-bounds or already occupied.
     */
    inline char add_object(CppGridObject* obj)
    {
        if (obj->location.row >= height || obj->location.col >= width || obj->location.layer >= num_layers)
            return false;
        if (grid[obj->location.row][obj->location.col][obj->location.layer] != 0) return false;

        obj->id = objects.size();
        objects.push_back(obj);
        grid[obj->location.row][obj->location.col][obj->location.layer] = obj->id;
        return true;
    }

    /**
     * Removes an object from the grid by pointer.
     *
     * WARNING: This function does not delete the object or reset its fields.
     * The object's ID and location remain valid, which may lead to undefined
     * behavior if the object is reused or re-added without updating these fields.
     *
     * Consider resetting obj->id to 0 after removal to mark it invalid,
     * or ensure that removed objects are not reused.
     */
    inline void remove_object(CppGridObject* obj)
    {
        grid[obj->location.row][obj->location.col][obj->location.layer] = 0;
        objects[obj->id] = nullptr;
    }

    /**
     * Remove an object by its ID.
     */
    inline void remove_object(cpp_GridObjectId id)
    {
        remove_object(objects[id]);
    }

    /**
     * Attempt to move an object to a new location.
     * Returns true if successful, false if out-of-bounds or destination occupied.
     */
    inline char move_object(cpp_GridObjectId id, const CppGridLocation& loc)
    {
        if (loc.row >= height || loc.col >= width || loc.layer >= num_layers) return false;
        if (grid[loc.row][loc.col][loc.layer] != 0) return false;

        CppGridObject* obj = objects[id];
        grid[loc.row][loc.col][loc.layer] = id;
        grid[obj->location.row][obj->location.col][obj->location.layer] = 0;
        obj->location = loc;
        return true;
    }

    /**
     * Swap two objects' positions, preserving layer context.
     */
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

        obj1->location = loc2;
        obj1->location.layer = layer1;
        obj2->location = loc1;
        obj2->location.layer = layer2;

        grid[obj1->location.row][obj1->location.col][obj1->location.layer] = id1;
        grid[obj2->location.row][obj2->location.col][obj2->location.layer] = id2;
    }

    /**
     * Get a pointer to the object by ID.
     */
    inline CppGridObject* object(cpp_GridObjectId obj_id)
    {
        return objects[obj_id];
    }

    /**
     * Get a pointer to the object at a specific location.
     * Returns nullptr if out-of-bounds or empty.
     */
    inline CppGridObject* object_at(const CppGridLocation& loc)
    {
        if (loc.row >= height || loc.col >= width || loc.layer >= num_layers) return nullptr;
        if (grid[loc.row][loc.col][loc.layer] == 0) return nullptr;
        return objects[grid[loc.row][loc.col][loc.layer]];
    }

    /**
     * Get the object at a location and of a specific type, or nullptr.
     */
    inline CppGridObject* object_at(const CppGridLocation& loc, cpp_TypeId type_id)
    {
        CppGridObject* obj = object_at(loc);
        return (obj && obj->objectTypeId == type_id) ? obj : nullptr;
    }

    /**
     * Overload: object at (row, col) of a specific type.
     */
    inline CppGridObject* object_at(cpp_GridCoord r, cpp_GridCoord c, cpp_TypeId type_id)
    {
        CppGridObject* obj = object_at(CppGridLocation(r, c), layer_for_type_id[type_id]);
        return (obj && obj->objectTypeId == type_id) ? obj : nullptr;
    }

    /**
     * Get the current location of the object by ID.
     */
    inline const CppGridLocation location(cpp_GridObjectId id)
    {
        return objects[id]->location;
    }

    /**
     * Compute a relative location offset from the given one.
     * Clamped to grid bounds. Does NOT check occupancy.
     */
    inline const CppGridLocation relative_location(const CppGridLocation& loc, cpp_Orientation orientation,
                                                   cpp_GridCoord distance, cpp_GridCoord offset)
    {
        int new_r = loc.row, new_c = loc.col;
        switch (orientation) {
            case Up:
                new_r -= distance;
                new_c -= offset;
                break;
            case Down:
                new_r += distance;
                new_c += offset;
                break;
            case Left:
                new_r += offset;
                new_c -= distance;
                break;
            case Right:
                new_r -= offset;
                new_c += distance;
                break;
        }
        new_r = max(0, new_r);
        new_c = max(0, new_c);
        return CppGridLocation(new_r, new_c, loc.layer);
    }

    /**
     * Overload: computes a relative location and updates layer based on type.
     */
    inline const CppGridLocation relative_location(const CppGridLocation& loc, cpp_Orientation orientation,
                                                   cpp_GridCoord distance, cpp_GridCoord offset, cpp_TypeId type_id)
    {
        CppGridLocation rloc = relative_location(loc, orientation, distance, offset);
        rloc.layer = layer_for_type_id[type_id];
        return rloc;
    }

    inline const CppGridLocation relative_location(const CppGridLocation& loc, cpp_Orientation orientation)
    {
        return relative_location(loc, orientation, 1, 0);
    }

    inline const CppGridLocation relative_location(const CppGridLocation& loc, cpp_Orientation orientation,
                                                   cpp_TypeId type_id)
    {
        return relative_location(loc, orientation, 1, 0, type_id);
    }

    /**
     * Returns true if all layers at (row, col) are unoccupied.
     */
    inline char is_empty(unsigned int row, unsigned int col)
    {
        CppGridLocation loc;
        loc.row = row;
        loc.col = col;
        for (int layer = 0; layer < num_layers; ++layer) {
            loc.layer = layer;
            if (object_at(loc)) return 0;
        }
        return 1;
    }
};

#endif  // CPP_GRID_HPP
