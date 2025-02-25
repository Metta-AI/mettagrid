#ifndef GENERATOR_HPP
#define GENERATOR_HPP

#include <vector>
#include <string>
#include "../grid_object.hpp"
#include "agent.hpp"
#include "constants.hpp"
#include "converter.hpp"

typedef unsigned char ObsType;

class Generator : public Converter {
public:
    Generator(GridCoord r, GridCoord c, ObjectConfig cfg) : Converter(r, c, cfg, ObjectType::GeneratorT) {
        this->recipe_input[InventoryItem::ore] = 1;
        this->recipe_output[InventoryItem::battery] = 1;
    }

    inline void use(Agent *actor, float *rewards) override {
        actor->update_inventory(InventoryItem::ore, -1, rewards);
        actor->update_inventory(InventoryItem::battery, 1, rewards);

        actor->stats.incr(InventoryItemNames[InventoryItem::ore], "used");
        actor->stats.incr(
            InventoryItemNames[InventoryItem::ore],
            "converted",
            InventoryItemNames[InventoryItem::battery]);

        actor->stats.incr(InventoryItemNames[InventoryItem::battery], "created");
    }
};

#endif
