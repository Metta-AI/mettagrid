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
    vector<unsigned char> input_inventory;
    vector<unsigned char> output_inventory;

    vector<unsigned char> recipe_input;
    vector<unsigned char> recipe_output;
    // For now, we hard code a converter's recipe, and use this indicator to let agents
    // know what the converter does.
    unsigned char type;
    unsigned char recipe_duration;
    bool converting;

    Converter(GridCoord r, GridCoord c, ObjectConfig cfg) {
        GridObject::init(ObjectType::ConverterT, GridLocation(r, c, GridLayer::Object_Layer));
        MettaObject::init_mo(cfg);
        Usable::init_usable(cfg);
        this->input_inventory.resize(InventoryItem::InventoryCount);
        this->output_inventory.resize(InventoryItem::InventoryCount);
        this->recipe_input.resize(InventoryItem::InventoryCount);
        this->recipe_output.resize(InventoryItem::InventoryCount);
        this->converting = false;
    }

    // returns true if we started converting. We do this so we can schedule our converting
    // to finish. It's more natural for us to scheule the finishing ourselves, but
    // it's harder to pass the env down to this code.
    // This should be called any time the converter could start converting. E.g.,
    // when things are added to its input, and when it finishes converting.
    bool maybe_start_converting() {
        if (!this->converting) {
            for (unsigned int i = 0; i < this->recipe_input.size(); i++) {
                if (this->input_inventory[i] < this->recipe_input[i]) {
                    return false;
                }
            }
            // produce
            for (unsigned int i = 0; i < this->recipe_input.size(); i++) {
                this->input_inventory[i] -= this->recipe_input[i];
            }
            this->converting = true;
            return true;
        }
        return false;
    }

    void finish_converting() {
        for (unsigned int i = 0; i < this->recipe_output.size(); i++) {
            this->output_inventory[i] += this->recipe_output[i];
        }
        this->converting = false;
    }

    static std::vector<std::string> feature_names() {
        return {"converter", "converter:type", "converter:converting", "converter:r1", "converter:r2", "converter:r3"};
    }
};
