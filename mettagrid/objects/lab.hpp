#ifndef LAB_HPP
#define LAB_HPP

#include <vector>
#include <string>
#include "../grid_object.hpp"
#include "agent.hpp"
#include "constants.hpp"
#include "converter.hpp"

class Lab : public Converter {
public:
    Lab(GridCoord r, GridCoord c, ObjectConfig cfg) : Converter(r, c, cfg, ObjectType::LabT) {
        this->recipe_input[InventoryItem::battery] = 3;
        this->recipe_input[InventoryItem::ore] = 3;
        this->recipe_output[InventoryItem::blueprint] = 1;
    }

    inline void use(Agent *actor, float *rewards) override {
        actor->update_inventory(InventoryItem::battery, -3, rewards);
        actor->update_inventory(InventoryItem::ore, -3, rewards);
        actor->update_inventory(InventoryItem::blueprint, 1, rewards);

        actor->stats.add(InventoryItemNames[InventoryItem::battery], "used", 3);
        actor->stats.add(InventoryItemNames[InventoryItem::ore], "used", 3);
        actor->stats.incr(InventoryItemNames[InventoryItem::blueprint], "created");

        actor->stats.add(
            InventoryItemNames[InventoryItem::battery],
            "converted",
            InventoryItemNames[InventoryItem::blueprint], 3);
        actor->stats.add(
            InventoryItemNames[InventoryItem::ore],
            "converted",
            InventoryItemNames[InventoryItem::blueprint], 3);
    }
};

#endif
