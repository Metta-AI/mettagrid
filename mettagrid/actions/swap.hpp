#ifndef SWAP_HPP
#define SWAP_HPP

#include <string>

#include "cpp_action_handler.hpp"
#include "cpp_grid.hpp"
#include "cpp_grid_object.hpp"
#include "objects/agent.hpp"

class Swap : public CppActionHandler {
public:
    Swap(const cpp_ActionConfig& cfg) : CppActionHandler(cfg, "swap") {}

    unsigned char cpp_max_arg() const override
    {
        return 0;
    }

protected:
    bool cpp_handle_action(unsigned int actor_id, Agent* actor, cpp_ActionArg arg) override
    {
        CppGridLocation target_loc =
            _grid->relative_location(actor->location, static_cast<cpp_Orientation>(actor->orientation));
        MettaObject* target = static_cast<MettaObject*>(_grid->object_at(target_loc));
        if (target == nullptr) {
            target_loc.layer = GridLayer::Object_Layer;
            target = static_cast<MettaObject*>(_grid->object_at(target_loc));
        }
        if (target == nullptr) {
            return false;
        }

        if (!target->swappable()) {
            return false;
        }

        actor->stats.incr("swap", _stats.target[target->objectTypeId]);

        _grid->swap_objects(actor->id, target->id);
        return true;
    }
};

#endif  // SWAP_HPP
