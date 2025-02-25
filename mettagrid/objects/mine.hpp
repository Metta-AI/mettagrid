#ifndef MINE_HPP
#define MINE_HPP

#include <vector>
#include <string>
#include "../grid_object.hpp"
#include "agent.hpp"
#include "constants.hpp"
#include "converter.hpp"

class Mine : public Converter {
public:
    Mine(GridCoord r, GridCoord c, ObjectConfig cfg) : Converter(r, c, cfg, ObjectType::MineT) {
        this->recipe_output[InventoryItem::ore] = 1;
    }

    inline void use(Agent *actor, float *rewards) override {
        actor->update_inventory(InventoryItem::ore, 1, rewards);
        actor->stats.incr(InventoryItemNames[InventoryItem::ore], "created");
    }
};

#endif
