#ifndef ARMORY_HPP
#define ARMORY_HPP

#include <vector>
#include <string>
#include "../grid_object.hpp"
#include "agent.hpp"
#include "constants.hpp"
#include "converter.hpp"

typedef unsigned char ObsType;

class Armory : public Converter {
public:
    Armory(GridCoord r, GridCoord c, ObjectConfig cfg) : Converter(r, c, cfg, ObjectType::ArmoryT) {
        this->recipe_input[InventoryItem::ore] = 3;
        this->recipe_output[InventoryItem::armor] = 1;
    }

    inline void use(Agent *actor, float *rewards) override {
        actor->update_inventory(InventoryItem::ore, -3, rewards);
        actor->update_inventory(InventoryItem::armor, 1, rewards);

        actor->stats.add(InventoryItemNames[InventoryItem::ore], "used", 3);
        actor->stats.incr(InventoryItemNames[InventoryItem::armor], "created");

        actor->stats.add(
            InventoryItemNames[InventoryItem::ore],
            "converted",
            InventoryItemNames[InventoryItem::armor], 3);
    }
};

#endif
