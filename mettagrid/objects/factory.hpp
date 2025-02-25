#ifndef FACTORY_HPP
#define FACTORY_HPP

#include <vector>
#include <string>
#include "../grid_object.hpp"
#include "agent.hpp"
#include "constants.hpp"
#include "converter.hpp"

class Factory : public Converter {
public:
    Factory(GridCoord r, GridCoord c, ObjectConfig cfg) : Converter(r, c, cfg, ObjectType::FactoryT) {
        this->recipe_input[InventoryItem::blueprint] = 1;
        this->recipe_input[InventoryItem::ore] = 5;
        this->recipe_input[InventoryItem::battery] = 5;
        this->recipe_output[InventoryItem::armor] = 5;
        this->recipe_output[InventoryItem::laser] = 5;
    }

    inline void use(Agent *actor, float *rewards) override {
        actor->update_inventory(InventoryItem::blueprint, -1, rewards);
        actor->update_inventory(InventoryItem::ore, -5, rewards);
        actor->update_inventory(InventoryItem::battery, -5, rewards);
        actor->update_inventory(InventoryItem::armor, 5, rewards);
        actor->update_inventory(InventoryItem::laser, 5, rewards);

        actor->stats.add(InventoryItemNames[InventoryItem::blueprint], "used", 1);
        actor->stats.add(InventoryItemNames[InventoryItem::armor], "created", 5);
        actor->stats.add(InventoryItemNames[InventoryItem::laser], "created", 5);
    }
};

#endif
