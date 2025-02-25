#ifndef LASERY_HPP
#define LASERY_HPP

#include <vector>
#include <string>
#include "../grid_object.hpp"
#include "agent.hpp"
#include "constants.hpp"
#include "converter.hpp"

typedef unsigned char ObsType;

class Lasery : public Converter {
public:
    Lasery(GridCoord r, GridCoord c, ObjectConfig cfg) : Converter(r, c, cfg, ObjectType::LaseryT) {
        this->recipe_input[InventoryItem::ore] = 1;
        this->recipe_input[InventoryItem::battery] = 2;
        this->recipe_output[InventoryItem::laser] = 1;
    }

    inline void use(Agent *actor, float *rewards) override {
        actor->update_inventory(InventoryItem::ore, -1, rewards);
        actor->update_inventory(InventoryItem::battery, -2, rewards);
        actor->update_inventory(InventoryItem::laser, 1, rewards);

        actor->stats.add(InventoryItemNames[InventoryItem::ore], "used", 1);
        actor->stats.add(InventoryItemNames[InventoryItem::battery], "used", 2);
        actor->stats.incr(InventoryItemNames[InventoryItem::laser], "created");
        actor->stats.add(
            InventoryItemNames[InventoryItem::ore],
            "converted",
            InventoryItemNames[InventoryItem::laser], 1);
        actor->stats.add(
            InventoryItemNames[InventoryItem::battery],
            "converted",
            InventoryItemNames[InventoryItem::laser], 2);
    }
};

#endif
