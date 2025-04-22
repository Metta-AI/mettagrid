#ifndef MOVE_HPP
#define MOVE_HPP

#include <string>

#include "action_handler.hpp"
#include "cpp_grid_object.hpp"
#include "objects/agent.hpp"

class Move : public ActionHandler {
public:
    Move(const ActionConfig& cfg) : ActionHandler(cfg, "move") {}

    unsigned char max_arg() const override
    {
        return 1;
    }

protected:
    bool _handle_action(unsigned int actor_id, Agent* actor, ActionArg arg) override
    {
        unsigned short direction = arg;

        cpp_Orientation orientation = static_cast<cpp_Orientation>(actor->orientation);
        if (direction == 1) {
            if (orientation == cpp_Orientation::Up) {
                orientation = cpp_Orientation::Down;
            }
            else if (orientation == cpp_Orientation::Down) {
                orientation = cpp_Orientation::Up;
            }
            else if (orientation == cpp_Orientation::Left) {
                orientation = cpp_Orientation::Right;
            }
            else if (orientation == cpp_Orientation::Right) {
                orientation = cpp_Orientation::Left;
            }
        }

        CppGridLocation old_loc = actor->location;
        CppGridLocation new_loc = _grid->relative_location(old_loc, orientation);
        if (!_grid->is_empty(new_loc.row, new_loc.col)) {
            return false;
        }
        return _grid->move_object(actor->id, new_loc);
    }
};

#endif  // MOVE_HPP
