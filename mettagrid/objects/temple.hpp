#ifndef TEMPLE_HPP
#define TEMPLE_HPP

#include <vector>
#include <string>
#include "../grid_object.hpp"
#include "agent.hpp"
#include "constants.hpp"
#include "converter.hpp"

class Temple : public Converter {
public:
    Temple(GridCoord r, GridCoord c, ObjectConfig cfg) : Converter(r, c, cfg, ObjectType::TempleT) {
        this->recipe_input[InventoryItem::heart] = 1;
        this->recipe_input[InventoryItem::blueprint] = 1;
        this->recipe_output[InventoryItem::heart] = 5;
    }

    inline void use(Agent *actor, float *rewards) override {
        actor->update_inventory(InventoryItem::heart, -1, rewards);
        actor->update_inventory(InventoryItem::blueprint, -1, rewards);
        actor->update_inventory(InventoryItem::heart, 5, rewards);

        actor->stats.add(InventoryItemNames[InventoryItem::heart], "used", 1);
        actor->stats.add(InventoryItemNames[InventoryItem::blueprint], "used", 1);
        actor->stats.add(InventoryItemNames[InventoryItem::heart], "created", 5);
    }
};

#endif
