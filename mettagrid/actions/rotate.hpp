#ifndef ROTATE_HPP
#define ROTATE_HPP

#include <string>

#include "cpp_action_handler.hpp"
#include "objects/agent.hpp"

class Rotate : public CppActionHandler {
public:
    Rotate(const cpp_ActionConfig& cfg) : CppActionHandler(cfg, "rotate") {}

    unsigned char cpp_max_arg() const override
    {
        return 3;
    }

protected:
    bool cpp_handle_action(unsigned int actor_id, Agent* actor, cpp_ActionArg arg) override
    {
        unsigned short orientation = arg;
        actor->orientation = orientation;
        return true;
    }
};

#endif  // ROTATE_HPP
