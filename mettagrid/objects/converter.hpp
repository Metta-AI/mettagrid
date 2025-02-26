#pragma once

#include <vector>
#include <string>
#include "../grid_object.hpp"
#include "constants.hpp"
#include "metta_object.hpp"
#include "usable.hpp"
#include "agent.hpp"

class Converter : public Usable {
public:
    vector<unsigned char> inventory;

    vector<unsigned char> recipe_input;
    vector<unsigned char> recipe_output;
    // the converter won't convert if its output already has this many things.
    // Mostly important for generators, probably?
    unsigned short max_output;
    unsigned char recipe_duration;
    bool converting;

    Converter(GridCoord r, GridCoord c, ObjectConfig cfg, TypeId type_id) {
        GridObject::init(type_id, GridLocation(r, c, GridLayer::Object_Layer));
        MettaObject::init_mo(cfg);
        Usable::init_usable(cfg);
        this->inventory.resize(InventoryItem::InventoryCount);
        this->recipe_input.resize(InventoryItem::InventoryCount);
        this->recipe_output.resize(InventoryItem::InventoryCount);
        this->max_output = 5;
        this->recipe_duration = 5;
        this->converting = false;
    }

    Converter(GridCoord r, GridCoord c, ObjectConfig cfg) : Converter(r, c, cfg, ObjectType::GenericConverterT) {}

    // returns true if we started converting. We do this so we can schedule our converting
    // to finish. It's more natural for us to scheule the finishing ourselves, but
    // it's harder to pass the env down to this code.
    // This should be called any time the converter could start converting. E.g.,
    // when things are added to its input, and when it finishes converting.
    bool maybe_start_converting() {
        if (!this->converting) {
            unsigned short total_output = 0;
            for (unsigned int i = 0; i < this->recipe_input.size(); i++) {
                if (this->inventory[i] < this->recipe_input[i]) {
                    return false;
                }
                if (this->recipe_output[i] > 0) {
                    total_output += this->inventory[i] / this->recipe_input[i];
                }
            }
            if (total_output >= this->max_output) {
                return false;
            }
            // produce.
            for (unsigned int i = 0; i < this->recipe_input.size(); i++) {
                this->inventory[i] -= this->recipe_input[i];
            }
            this->converting = true;
            return true;
        }
        return false;
    }

    void finish_converting() {
        for (unsigned int i = 0; i < this->recipe_output.size(); i++) {
            this->inventory[i] += this->recipe_output[i];
        }
        this->converting = false;
    }

    void obs(ObsType *obs) const override {
        obs[0] = 1;
        obs[1] = this->_type_id;
        obs[2] = this->hp;
        obs[3] = this->converting;
        for (unsigned int i = 0; i < InventoryItem::InventoryCount; i++) {
            obs[4 + i] = this->inventory[i];
        }
    }

    static std::vector<std::string> feature_names() {
        std::vector<std::string> names;
        // We use the same feature names for all converters, since this compresses
        // the observation space. At the moment we don't expose the recipe, since
        // we expect converters to be hard coded.
        // xcxc consider retaining the 1-hot encoding of the recipe.
        names.push_back("converter");
        names.push_back("converter:type");
        names.push_back("hp");
        names.push_back("converting");
        for (unsigned int i = 0; i < InventoryItem::InventoryCount; i++) {
            names.push_back(InventoryItemNames[i]);
        }
        return names;
    }
};
