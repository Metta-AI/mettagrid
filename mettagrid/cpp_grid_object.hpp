#ifndef CPP_GRID_OBJECT_HPP
#define CPP_GRID_OBJECT_HPP

#include <string>
#include <vector>

using namespace std;

/**
 * Type definitions for grid-related data
 */
typedef unsigned short cpp_Layer;       ///< Layer identifier type
typedef unsigned short cpp_TypeId;      ///< Object type identifier
typedef unsigned int cpp_GridCoord;     ///< Grid coordinate type
typedef unsigned char cpp_ObsType;      ///< Observation data type
typedef unsigned int cpp_GridObjectId;  ///< Unique grid object identifier

/**
 * @class CppGridLocation
 * @brief Represents a location in a multi-layered grid
 *
 * Stores row, column, and layer information for positioning objects within a grid
 */
class CppGridLocation {
public:
    cpp_GridCoord row;  ///< Row coordinate
    cpp_GridCoord col;  ///< Column coordinate
    cpp_Layer layer;    ///< Layer identifier

    /**
     * @brief Construct a location with row, column, and layer
     * @param row Row coordinate
     * @param col Column coordinate
     * @param layer Layer identifier
     */
    inline CppGridLocation(cpp_GridCoord row, cpp_GridCoord col, cpp_Layer layer) : row(row), col(col), layer(layer) {}

    /**
     * @brief Construct a location with row and column (layer defaults to 0)
     * @param row Row coordinate
     * @param col Column coordinate
     */
    inline CppGridLocation(cpp_GridCoord row, cpp_GridCoord col) : row(row), col(col), layer(0) {}

    /**
     * @brief Default constructor (0,0,0)
     */
    inline CppGridLocation() : row(0), col(0), layer(0) {}
};

/**
 * @enum cpp_Orientation
 * @brief Cardinal directions for object orientation
 */
enum cpp_Orientation {
    Up = 0,    ///< Facing upward
    Down = 1,  ///< Facing downward
    Left = 2,  ///< Facing left
    Right = 3  ///< Facing right
};

/**
 * @class CppGridObject
 * @brief Abstract base class for objects that exist on a grid
 *
 * Defines the interface and common functionality for all grid-based objects
 */
class CppGridObject {
public:
    cpp_GridObjectId id;       ///< Unique object identifier
    CppGridLocation location;  ///< Current grid location
    cpp_TypeId objectTypeId;   ///< Type identifier for this object

    /**
     * @brief Virtual destructor
     */
    virtual ~CppGridObject() = default;

    /**
     * @brief Initialize the object with a type and location
     * @param typeId Type identifier
     * @param loc Grid location
     */
    void cpp_init(cpp_TypeId typeId, const CppGridLocation& loc)
    {
        this->objectTypeId = typeId;
        this->location = loc;
    }

    /**
     * @brief Initialize the object with a type and row/column coordinates (layer=0)
     * @param typeId Type identifier
     * @param row Row coordinate
     * @param col Column coordinate
     */
    void cpp_init(cpp_TypeId typeId, cpp_GridCoord row, cpp_GridCoord col)
    {
        cpp_init(typeId, CppGridLocation(row, col, 0));
    }

    /**
     * @brief Initialize the object with a type, row/column coordinates, and layer
     * @param typeId Type identifier
     * @param row Row coordinate
     * @param col Column coordinate
     * @param layer Layer identifier
     */
    void cpp_init(cpp_TypeId typeId, cpp_GridCoord row, cpp_GridCoord col, cpp_Layer layer)
    {
        cpp_init(typeId, CppGridLocation(row, col, layer));
    }

    /**
     * @brief Generate observations about this object
     * @param observations Pointer to observation array to be filled
     * @param offsets Vector of observation indices/offsets
     */
    virtual void cpp_obs(cpp_ObsType* observations, const vector<unsigned int>& offsets) const = 0;
};

/**
 * @class CppTestGridObject
 * @brief Concrete implementation of CppGridObject for testing purposes
 *
 * Provides a simple implementation that generates test observations based on location
 */
class CppTestGridObject : public CppGridObject {
public:
    /**
     * @brief Implementation of the observation method for testing
     * @param observations Pointer to observation array to be filled
     * @param offsets Vector of observation indices/offsets
     */
    void cpp_obs(cpp_ObsType* observations, const vector<unsigned int>& offsets) const override
    {
        if (!offsets.empty()) {
            for (size_t i = 0; i < offsets.size(); ++i) {
                // Simple test logic: observation = row + col + offset index
                observations[i] = static_cast<cpp_ObsType>(location.row + location.col + i);
            }
        }
    }

    /**
     * @brief Alternative implementation with an ignored dummy parameter to avoid ambiguity
     * @param observations Pointer to observation array to be filled
     * @param offsets Vector of observation indices/offsets
     * @param dummy Ignored parameter to create a distinct signature
     */
    void cpp_obs(cpp_ObsType* observations, const vector<unsigned int>& offsets, int dummy) const
    {
        cpp_obs(observations, offsets);
    }
};

#endif  // CPP_GRID_OBJECT_HPP