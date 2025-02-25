#ifndef ALTAR_HPP
#define ALTAR_HPP

#include <vector>
#include <string>
#include "../grid_object.hpp"
#include "agent.hpp"
#include "constants.hpp"
#include "converter.hpp"

class Altar : public Converter {
public:
    Altar(GridCoord r, GridCoord c, ObjectConfig cfg) : Converter(r, c, cfg, ObjectType::AltarT) {
        this->recipe_input[InventoryItem::battery] = 3;
        this->recipe_output[InventoryItem::heart] = 1;
    }

    inline void use(Agent *actor, float *rewards) override {
        actor->update_inventory(InventoryItem::battery, -3, rewards);
        actor->update_inventory(InventoryItem::heart, 1, rewards);

        actor->stats.add(InventoryItemNames[InventoryItem::battery], "used", 3);
        actor->stats.incr(InventoryItemNames[InventoryItem::heart], "created");
        actor->stats.add(
            InventoryItemNames[InventoryItem::battery],
            "converted",
            InventoryItemNames[InventoryItem::heart], 3);
    }
};

#endif
